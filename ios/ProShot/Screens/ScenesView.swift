import SwiftUI

/// Выбор сцен в рамках купленного тарифа: не больше max_scenes.
/// Сервер проверяет это же число и вернёт 400, если прислать больше.
struct ScenesView: View {
    @Binding var path: [Route]
    @Environment(AppState.self) private var state

    var body: some View {
        ScreenScaffold(title: L("scenes_title"), subtitle: subtitle) {
            if let pkg = state.selectedPackage {
                SceneGrid(scenes: state.availableScenes,
                          selected: Set(state.selectedScenes)) { key in
                    state.toggleScene(key)
                }
                .id(pkg.sku)
            } else {
                Text(L("scenes_no_pkg")).foregroundStyle(.secondary)
            }
        } bottom: {
            PrimaryButton(title: L("scenes_next"),
                          enabled: !state.selectedScenes.isEmpty) {
                path.append(.summary)
            }
        }
    }

    private var subtitle: String {
        guard let pkg = state.selectedPackage else { return L("scenes_pick_min") }
        if state.selectedScenes.isEmpty {
            return L("scenes_subtitle_empty", pkg.title, pkg.maxScenes)
        }
        return L("scenes_subtitle",
                 pkg.title, pkg.maxScenes, state.selectedScenes.count,
                 state.photosPerScene, pkg.totalPhotos)
    }
}
