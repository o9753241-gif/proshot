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
                        .font(.largeTitle.bold())
                        .fixedSize(horizontal: false, vertical: true)
                    if let subtitle {
                        Text(subtitle)
                            .font(.subheadline)
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
                Text(title).font(.headline)
            }
            .frame(maxWidth: .infinity, minHeight: 50)
        }
        .buttonStyle(.borderedProminent)
        .disabled(!enabled || loading)
    }
}
