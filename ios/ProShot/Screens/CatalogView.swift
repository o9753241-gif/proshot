import SwiftUI

/// Каталог целиком. Сначала сцены выбранной профессии, следом остальные —
/// ничего не спрятано, подборка только меняет порядок.
struct CatalogView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    var body: some View {
        ScreenScaffold(title: state.industryTitle,
                       subtitle: L("catalog_subtitle", state.styles.count)) {
            if state.isLoading && state.styles.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            } else if let error = state.errorMessage, state.styles.isEmpty {
                ErrorBlock(message: error) { Task { await state.bootstrap() } }
            } else {
                let recommended = state.recommended(from: state.styles)
                let others = state.others(from: state.styles)

                if !recommended.isEmpty {
                    SceneSection(title: L("catalog_recommended"),
                                 note: L("catalog_recommended_note"),
                                 scenes: recommended)
                }
                if !others.isEmpty {
                    SceneSection(title: recommended.isEmpty ? L("catalog_all") : L("catalog_other"),
                                 note: nil,
                                 scenes: others)
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

/// Озаглавленный кусок каталога.
private struct SceneSection: View {
    let title: String
    let note: String?
    let scenes: [StyleDTO]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(.inter(20, .semibold))
                Spacer()
                Text(L("catalog_count", scenes.count))
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
            }
            if let note {
                Text(note)
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            SceneGrid(scenes: scenes)
        }
        .padding(.top, 8)
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
