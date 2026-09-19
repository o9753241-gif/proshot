import SwiftUI
import StoreKit

/// Выбор тарифа. Цена берётся из StoreKit, а не с сервера: она в валюте
/// витрины пользователя и всегда совпадает с тем, что спишет Apple.
/// Серверная price_display остаётся запасным вариантом, пока товары не загрузились.
struct PackagesView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState
    @EnvironmentObject private var purchases: PurchaseManager

    var body: some View {
        ScreenScaffold(title: L("packages_title"), subtitle: L("packages_subtitle")) {
            ForEach(state.packages) { pkg in
                Button {
                    state.selectedPackage = pkg
                    state.selectedScenes = []
                    path.append(.scenes)
                } label: {
                    PackageRow(pkg: pkg, price: price(for: pkg))
                }
                .buttonStyle(.plain)
            }
        }
        .task { await purchases.loadProducts() }
    }

    private func price(for pkg: PackageDTO) -> String {
        purchases.products.first { $0.id == pkg.sku }?.displayPrice ?? pkg.priceDisplay
    }
}

private struct PackageRow: View {
    let pkg: PackageDTO
    let price: String

    /// «Стандарт» помечен как хит — так же, как в Android-версии.
    private var isHit: Bool { pkg.sku == "pack_standard" }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(pkg.title).font(.inter(20, .semibold))
                if isHit {
                    Text(L("pkg_hit"))
                        .font(.inter(11, .medium))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Color.accentColor, in: Capsule())
                        .foregroundStyle(.white)
                }
                Spacer()
                Text(price).font(.inter(20, .semibold))
            }
            Text(L("pkg_photos", pkg.totalPhotos)).font(.inter(14))
            Text(L("pkg_scenes_line", pkg.maxScenes, pkg.scenesPool))
                .font(.inter(12)).foregroundStyle(.secondary)
            HStack {
                Spacer()
                Text(L("pkg_choose")).font(.inter(16, .semibold)).foregroundStyle(Color.accentColor)
            }
        }
        .padding(16)
        .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder(isHit ? Color.accentColor : .clear, lineWidth: 2)
        }
    }
}
