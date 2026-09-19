import SwiftUI

/// Общая обвязка экрана: заголовок, подзаголовок, отступы.
/// Аналог ScreenScaffold.kt из Android-версии.
struct ScreenScaffold<Content: View, Bottom: View>: View {
    let title: String
    var subtitle: String?
    @ViewBuilder var content: () -> Content
    @ViewBuilder var bottom: () -> Bottom

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(title)
                        .font(.inter(32, .bold))
                        .fixedSize(horizontal: false, vertical: true)
                    if let subtitle {
                        Text(subtitle)
                            .font(.inter(14))
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    content()
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(20)
            }
            bottom()
                .padding(20)
                .background(.bar)
        }
        .navigationBarTitleDisplayMode(.inline)
    }
}

extension ScreenScaffold where Bottom == EmptyView {
    init(title: String, subtitle: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.init(title: title, subtitle: subtitle, content: content, bottom: { EmptyView() })
    }
}

/// Кнопка основного действия — одна на экран, внизу.
struct PrimaryButton: View {
    let title: String
    var enabled: Bool = true
    var loading: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if loading { ProgressView().tint(.white) }
                Text(title).font(.inter(18, .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 50)
        }
        .buttonStyle(.borderedProminent)
        .disabled(!enabled || loading)
    }
}

// ── Палитра ──────────────────────────────────────────────────────────
//
// Значения взяты из Android-версии (`ui/theme/Color.kt`), а не подобраны
// на глаз: иначе iOS-сборка выглядит чужой рядом с той же самой программой
// на другом телефоне.
enum Palette {
    /// BrandPrimary #3B5BFF — синий, основной цвет действия.
    static let primary = Color(red: 0x3B / 255, green: 0x5B / 255, blue: 0xFF / 255)
    /// BrandSecondary #0F1226 — почти чёрный, заголовки.
    static let ink = Color(red: 0x0F / 255, green: 0x12 / 255, blue: 0x26 / 255)
    /// BrandBg #F7F8FC — светлый фон.
    static let background = Color(red: 0xF7 / 255, green: 0xF8 / 255, blue: 0xFC / 255)
    /// BrandSurface — карточки.
    static let surface = Color.white
    /// BrandMuted #6B7280 — второстепенный текст.
    static let muted = Color(red: 0x6B / 255, green: 0x72 / 255, blue: 0x80 / 255)
    /// Заливка плейсхолдеров (#ECEEF5). Замена .background.secondary,
    /// которая доступна только с iOS 17.
    static let fill = Color(red: 0xEC / 255, green: 0xEE / 255, blue: 0xF5 / 255)
}

// ── Шрифт ────────────────────────────────────────────────────────────
//
// Inter, тот же и в тех же четырёх начертаниях, что в Android-версии.
// Обращаемся по имени PostScript: у начертаний Medium и SemiBold семейство
// своё, и запрос по имени семейства с указанием веса даёт не то.
extension Font {
    static func inter(_ size: CGFloat, _ weight: Weight = .regular) -> Font {
        let name: String
        switch weight {
        case .bold, .heavy, .black: name = "Inter-Bold"
        case .semibold:             name = "Inter-SemiBold"
        case .medium:               name = "Inter-Medium"
        default:                    name = "Inter-Regular"
        }
        return .custom(name, size: size)
    }
}
