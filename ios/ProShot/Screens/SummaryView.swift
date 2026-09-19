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
                    Text(pkg.title).font(.inter(20, .semibold))
                    Text(L("summary_recap",
                           state.selectedScenes.count,
                           state.photosPerScene,
                           pkg.totalPhotos))
                        .font(.inter(14))
                        .foregroundStyle(.secondary)
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))

                SceneGrid(scenes: state.selectedScenes.compactMap(state.scene(for:)))

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
        product?.displayPrice ?? state.selectedPackage?.priceDisplay ?? ""
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
        case .success:
            paying = false
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
