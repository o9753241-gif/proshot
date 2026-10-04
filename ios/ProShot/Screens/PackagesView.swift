import SwiftUI
import StoreKit

/// Выбор тарифа. Цена берётся только из StoreKit: она в валюте витрины
/// пользователя и всегда совпадает с тем, что спишет Apple. Серверную
/// price_display не показываем даже как запасной вариант: она в рублях
/// по языку, а не по стране, и человек из США видел бы «990 ₽».
/// Пока товар не загрузился, цена просто пустая.
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
                    PackageRow(pkg: pkg, product: product(for: pkg))
                }
                .buttonStyle(.plain)
            }
        }
        .task { await purchases.loadProducts() }
    }

    private func product(for pkg: PackageDTO) -> Product? {
        purchases.products.first { $0.id == pkg.sku }
    }
}

private struct PackageRow: View {
    let pkg: PackageDTO
    /// Товар StoreKit. Пока не загрузился — цены нет вовсе (см. выше).
    let product: Product?

    /// «Стандарт» помечен как хит — так же, как в Android-версии.
    private var isHit: Bool { pkg.sku == "pack_standard" }
    /// Самая низкая цена за фото — у самого большого пакета.
    private var isBest: Bool { pkg.sku == "pack_premium" }

    /// Цена за одно фото в валюте витрины. Больше 10 единиц — без копеек.
    private var perPhoto: String? {
        guard let product, pkg.totalPhotos > 0 else { return nil }
        let value = product.price / Decimal(pkg.totalPhotos)
        let style = product.priceFormatStyle.precision(.fractionLength(value >= 10 ? 0 : 2))
        return L("pkg_per_photo", value.formatted(style))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(pkg.title).font(.inter(17, .semibold))
                if isHit { badge(L("pkg_hit"), Color.accentColor) }
                if isBest { badge(L("pkg_best"), .green) }
                Spacer(minLength: 8)
                Text(product?.displayPrice ?? "").font(.inter(18, .semibold))
            }
            HStack(alignment: .lastTextBaseline) {
                HStack(alignment: .lastTextBaseline, spacing: 6) {
                    Text("\(pkg.totalPhotos)").font(.inter(34, .bold))
                    Text(L("pkg_unit")).font(.inter(15, .medium))
                }
                Spacer(minLength: 8)
                if let perPhoto {
                    Text(perPhoto)
                        .font(.inter(13))
                        .foregroundStyle(isBest ? Color.green : Color.secondary)
                }
            }
            HStack {
                Text(L("pkg_scenes_line", pkg.maxScenes, pkg.scenesPool))
                    .font(.inter(13)).foregroundStyle(.secondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
        .overlay {
            RoundedRectangle(cornerRadius: 14)
                .strokeBorder(isHit ? Color.accentColor : .clear, lineWidth: 2)
        }
        .contentShape(RoundedRectangle(cornerRadius: 14))
    }

    private func badge(_ text: String, _ color: Color) -> some View {
        Text(text)
            .font(.inter(11, .semibold))
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color, in: Capsule())
            .foregroundStyle(.white)
            .lineLimit(1)
            .fixedSize()
    }
}
