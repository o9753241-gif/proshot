import SwiftUI

/// Все сгенерированные снимки. Живут только в этой сессии: на сервере
/// результаты удаляются через сутки, и приложение их не кэширует.
struct GalleryView: View {
    @EnvironmentObject private var state: AppState
    @State private var toast: String?

    private let columns = [GridItem(.adaptive(minimum: 108), spacing: 10)]

    var body: some View {
        ScreenScaffold(title: L("gallery_title"),
                       subtitle: L("gallery_subtitle", state.totalGenerated)) {
            if state.results.isEmpty {
                Text(L("gallery_empty"))
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
            } else {
                if let toast {
                    Text(toast).font(.inter(13)).foregroundStyle(.secondary)
                }
                LazyVGrid(columns: columns, spacing: 10) {
                    ForEach(allPhotos, id: \.self) { url in
                        CachedImage(url: url) {
                            Rectangle().fill(.quaternary)
                        }
                        .aspectRatio(1, contentMode: .fill)
                        .clipped()
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .contextMenu {
                            Button(L("action_save")) {
                                Task {
                                    let ok = await PhotoSaver.save(from: url)
                                    toast = ok ? L("result_saved_ok") : L("result_saved_fail")
                                }
                            }
                            ShareLink(item: url) { Text(L("action_share")) }
                        }
                    }
                }
            }
        }
    }

    /// Порядок стабильный: сцены в том порядке, в каком их выбрали.
    private var allPhotos: [URL] {
        state.selectedScenes.flatMap { state.results[$0] ?? [] }
    }
}
