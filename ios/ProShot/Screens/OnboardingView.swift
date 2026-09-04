import SwiftUI

/// Три страницы, как в Android-версии. Тексты те же.
struct OnboardingView: View {
    let onFinish: () -> Void
    @State private var page = 0

    private let pages = [
        (L("onb_1_title"), L("onb_1_body")),
        (L("onb_2_title"), L("onb_2_body")),
        (L("onb_3_title"), L("onb_3_body")),
    ]

    var body: some View {
        VStack {
            HStack {
                Spacer()
                Button(L("onb_skip"), action: onFinish)
                    .padding()
            }

            TabView(selection: $page) {
                ForEach(pages.indices, id: \.self) { index in
                    VStack(alignment: .leading, spacing: 16) {
                        Spacer()
                        Text(pages[index].0)
                            .font(.largeTitle.bold())
                            .fixedSize(horizontal: false, vertical: true)
                        Text(pages[index].1)
                            .font(.body)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(28)
                    .tag(index)
                }
            }
            .tabViewStyle(.page)

            PrimaryButton(title: page == pages.count - 1 ? L("onb_start") : L("onb_next")) {
                if page == pages.count - 1 { onFinish() } else { page += 1 }
            }
            .padding(20)
        }
    }
}
