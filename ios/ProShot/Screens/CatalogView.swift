import SwiftUI

/// Каталог сцен, сгруппированный по тарифам. Первый экран после онбординга.
struct CatalogView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    private let tiers: [(tier: Int, name: String, note: String)] = [
        (1, L("tier_basic"),    L("tier_desc_basic")),
        (2, L("tier_standard"), L("tier_desc_standard")),
        (3, L("tier_premium"),  L("tier_desc_premium")),
    ]

    var body: some View {
        ScreenScaffold(title: L("catalog_title"), subtitle: L("catalog_subtitle")) {
            if state.isLoading && state.styles.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            } else if let error = state.errorMessage, state.styles.isEmpty {
                ErrorBlock(message: error) { Task { await state.bootstrap() } }
            } else {
                ForEach(tiers, id: \.tier) { tier in
                    let scenes = state.styles.filter { $0.tier == tier.tier }
                    if !scenes.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(alignment: .firstTextBaseline) {
                                Text(tier.name).font(.inter(20, .semibold))
                                Spacer()
                                Text(tier.tier == 1
                                     ? L("tier_count_first", scenes.count)
                                     : L("tier_count_more", scenes.count))
                                    .font(.inter(12))
                                    .foregroundStyle(.secondary)
                            }
                            Text(tier.note).font(.inter(12)).foregroundStyle(.secondary)
                            SceneGrid(scenes: scenes)
                        }
                        .padding(.top, 8)
                    }
                }
            }
        } bottom: {
            PrimaryButton(title: L("catalog_continue"),
                          enabled: !state.styles.isEmpty) {
                path.append(.packages)
            }
        }
    }
}

/// Сетка превью сцен. Одинаковая на каталоге и на выборе сцен.
struct SceneGrid: View {
    let scenes: [StyleDTO]
    var selected: Set<String> = []
    var onTap: ((String) -> Void)?

    private let columns = [GridItem(.adaptive(minimum: 104), spacing: 10)]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 10) {
            ForEach(scenes) { scene in
                VStack(spacing: 6) {
                    ZStack(alignment: .topTrailing) {
                        CachedImage(url: URL(string: scene.previewUrl)) {
                            Rectangle().fill(.quaternary)
                        }
                        .aspectRatio(1, contentMode: .fill)
                        .clipped()
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .overlay {
                            RoundedRectangle(cornerRadius: 10)
                                .strokeBorder(selected.contains(scene.key) ? Color.accentColor : .clear,
                                              lineWidth: 3)
                        }

                        if selected.contains(scene.key) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.white, Color.accentColor)
                                .padding(6)
                        }
                    }
                    Text(scene.title)
                        .font(.inter(11))
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                }
                .contentShape(Rectangle())
                .onTapGesture { onTap?(scene.key) }
            }
        }
    }
}

struct ErrorBlock: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Text(message).font(.inter(14)).multilineTextAlignment(.center)
            Button(L("retry"), action: retry).buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
}
