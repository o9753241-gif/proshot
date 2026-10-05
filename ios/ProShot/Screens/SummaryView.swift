import SwiftUI
import StoreKit

/// Превью заказа и оплата. Единственное место, где начинается покупка.
struct SummaryView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState
    @EnvironmentObject private var purchases: PurchaseManager

    @State private var paying = false
    @State private var message: String?
    @State private var serverPending = false

    var body: some View {
        ScreenScaffold(title: L("summary_title"), subtitle: L("summary_subtitle")) {
            if let pkg = state.selectedPackage {
                VStack(alignment: .leading, spacing: 12) {
                    // Цена рядом с названием, как в Android (SummaryScreen).
                    HStack(alignment: .firstTextBaseline) {
                        Text(pkg.title).font(.inter(20, .semibold))
                        Spacer(minLength: 8)
                        Text(priceText).font(.inter(24, .bold))
                    }
                    // Числа со словами через stringsdict: «3 сцены», а не «3 сцен».
                    Text(L("summary_recap",
                           L("n_scenes", state.selectedScenes.count),
                           state.photosPerScene,
                           L("n_shots", pkg.totalPhotos)))
                        .font(.inter(14))
                        .foregroundStyle(.secondary)
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))

                SceneGrid(scenes: state.selectedScenes.compactMap(state.scene(for:)))

                NextSteps(photosPerScene: state.photosPerScene)

                if serverPending {
                    Text(L("billing_server_pending"))
                        .font(.inter(13))
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.yellow.opacity(0.18), in: RoundedRectangle(cornerRadius: 10))
                }
                if let message {
                    Text(message).font(.inter(13)).foregroundStyle(.red)
                }
            }
        } bottom: {
            PrimaryButton(title: paying ? L("summary_paying") : L("summary_pay", priceText),
                          enabled: product != nil,
                          loading: paying) {
                Task { await pay() }
            }
        }
        .task { await purchases.loadProducts() }
    }

    private var product: Product? {
        guard let sku = state.selectedPackage?.sku else { return nil }
        return purchases.products.first { $0.id == sku }
    }

    private var priceText: String {
        // Только цена StoreKit, см. PackagesView. Без товара кнопка и так неактивна.
        product?.displayPrice ?? ""
    }

    private func pay() async {
        guard let product, let pkg = state.selectedPackage else { return }
        paying = true
        message = nil
        serverPending = false

        // Выбор сцен сохраняется ДО оплаты: если приложение закроется между
        // списанием денег и ответом сервера, восстановление возьмёт его отсюда.
        SceneSelectionStore.save(state.selectedScenes, for: pkg.sku)

        switch await purchases.purchase(product, scenes: state.selectedScenes) {
        case .success(let purchase):
            paying = false
            state.activePurchase = purchase
            path.append(.capture)
        case .cancelled:
            paying = false
        case .pending:
            paying = false
            message = L("billing_not_finished")
        case .failed(let reason):
            paying = false
            // Деньги могли уже списаться: транзакция осталась незакрытой и
            // вернётся при следующем запуске. Об этом и говорим.
            serverPending = true
            message = reason
        }
    }
}

/// «Что будет после оплаты»: съёмка с проверкой кадра, варианты в каждой
/// сцене, четыре формата. Человек видит, за что платит, а это ровно то, чем
/// ProShot отличается от приложений «загрузи селфи — получи фото» (App Store 4.3).
private struct NextSteps: View {
    let photosPerScene: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(L("summary_next_title")).font(.inter(18, .semibold))
            step(1, "camera.viewfinder", L("summary_next_1"))
            step(2, "photo.stack", L("summary_next_2", photosPerScene))
            step(3, "rectangle.3.group", L("summary_next_3"))
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
        .padding(.top, 4)
    }

    private func step(_ number: Int, _ symbol: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: symbol)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(Color.accentColor)
                .frame(width: 32, height: 32)
                .background(Color.accentColor.opacity(0.15), in: Circle())
                .accessibilityHidden(true)
            Text(text)
                .font(.inter(14))
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 6)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(number). \(text)")
    }
}
