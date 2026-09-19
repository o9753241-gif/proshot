import SwiftUI

/// Генерация по одной сцене за раз, как в Android-версии.
///
/// Автоматической очереди нет намеренно: человек выбирает сцену, смотрит
/// результат и решает, тратить ли следующий снимок. Бюджет пакета виден всегда.
struct ResultView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    @State private var currentScene: String?
    @State private var latest: URL?
    @State private var generating = false
    @State private var error: String?
    @State private var toast: String?
    @State private var showExit = false

    var body: some View {
        ScreenScaffold(title: title, subtitle: subtitle) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(.background.secondary)
                    .aspectRatio(1, contentMode: .fit)

                if generating {
                    VStack(spacing: 10) {
                        ProgressView()
                        Text(currentScene.flatMap { state.scene(for: $0)?.title }
                             .map { L("result_generating", $0) } ?? L("result_generating_short"))
                            .font(.inter(13)).foregroundStyle(.secondary)
                    }
                } else if let latest {
                    CachedImage(url: latest) {
                        ProgressView()
                    }
                    .aspectRatio(contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                } else {
                    Text(L("result_pick_scene_hint"))
                        .font(.inter(16))
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(24)
                }
            }

            if let latest {
                HStack(spacing: 12) {
                    Button(L("result_save")) {
                        Task {
                            let ok = await PhotoSaver.save(from: latest)
                            toast = ok ? L("result_saved_ok") : L("result_saved_fail")
                        }
                    }
                    .buttonStyle(.bordered)

                    ShareLink(item: latest) { Text(L("result_share")) }
                        .buttonStyle(.bordered)
                }
            }

            if let error {
                Text(error).font(.inter(13)).foregroundStyle(.red)
            }
            if let toast {
                Text(toast).font(.inter(13)).foregroundStyle(.secondary)
            }

            // Выбранные сцены: нажатие тратит один снимок из пакета.
            Text(L("result_next_scene")).font(.inter(18, .semibold)).padding(.top, 8)
            SceneGrid(scenes: state.selectedScenes.compactMap(state.scene(for:)),
                      selected: Set([currentScene].compactMap { $0 })) { key in
                guard !generating, state.remainingBudget > 0 else { return }
                Task { await generate(scene: key) }
            }
        } bottom: {
            HStack(spacing: 12) {
                Button(L("result_all_photos", state.totalGenerated)) {
                    path.append(.gallery)
                }
                .buttonStyle(.bordered)
                .disabled(state.totalGenerated == 0)

                Button(L("result_home")) { showExit = true }
                    .buttonStyle(.bordered)
            }
        }
        .alert(L("result_exit_title"), isPresented: $showExit) {
            Button(L("result_exit_yes"), role: .destructive) {
                state.startOver()
                path.removeAll()
            }
            Button(L("result_exit_no"), role: .cancel) {}
        } message: {
            Text(L("result_exit_body", state.totalGenerated, state.remainingBudget))
        }
    }

    private var title: String {
        state.remainingBudget == 0 && state.totalGenerated > 0
            ? L("result_all_done_title")
            : L("result_pick_scene_title")
    }

    private var subtitle: String {
        L("result_subtitle_progress", state.totalGenerated,
          state.selectedPackage?.totalPhotos ?? 0)
    }

    private func generate(scene key: String) async {
        guard let photo = state.photoData else {
            error = L("result_error_no_data")
            return
        }
        currentScene = key
        generating = true
        error = nil
        toast = nil
        defer { generating = false }

        do {
            let response = try await ProShotAPI.shared.generate(
                sceneKey: key,
                imageData: photo,
                heightCm: state.heightCm,
                weightKg: state.weightKg
            )
            if let url = URL(string: response.imageUrl) {
                state.results[key, default: []].append(url)
                latest = url
            }
        } catch let apiError as APIError {
            // 402 и 429 сервер отдаёт кодами, а не текстом: показываем причину,
            // а не общую «ошибка генерации».
            error = apiError.errorDescription
        } catch {
            self.error = L("result_error_generation")
        }
    }
}
