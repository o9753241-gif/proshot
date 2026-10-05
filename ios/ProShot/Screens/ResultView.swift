import SwiftUI

/// Генерация по одной сцене за раз.
///
/// Автоматической очереди нет намеренно: человек выбирает сцену, смотрит
/// результат и решает, тратить ли следующий снимок. Выбор и запуск разделены
/// (решение владельца): нажатие на сцену только выделяет её, фото списывается
/// по отдельной кнопке, под которой видно, сколько останется. Раньше нажатие
/// на сцену сразу запускало генерацию, и фото уходило случайным касанием.
struct ResultView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    @State private var currentScene: String?
    /// Сцена, выделенная для следующей генерации. Ничего не списывает.
    @State private var pickedScene: String?
    @State private var latest: URL?
    @State private var generating = false
    @State private var error: String?
    @State private var toast: String?
    @State private var showExit = false

    var body: some View {
        ScreenScaffold(title: title, subtitle: subtitle) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(Palette.fill)
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

                // Главное действие после удачного кадра: разложить его по
                // рабочим форматам. Считается на устройстве, фото не тратит.
                Button(L("result_crops")) {
                    state.cropSource = latest
                    path.append(.cropSet)
                }
                .buttonStyle(.borderedProminent)
            }

            if let error {
                Text(error).font(.inter(13)).foregroundStyle(.red)
            }
            if let toast {
                Text(toast).font(.inter(13)).foregroundStyle(.secondary)
            }

            // Выбранные при оплате сцены. Нажатие только выделяет сцену.
            Text(L("result_next_scene")).font(.inter(18, .semibold)).padding(.top, 8)
            SceneGrid(scenes: state.selectedScenes.compactMap(state.scene(for:)),
                      selected: Set([pickedScene].compactMap { $0 })) { key in
                guard !generating else { return }
                pickedScene = key
            }
        } bottom: {
          VStack(spacing: 12) {
            VStack(spacing: 8) {
                PrimaryButton(title: generateTitle,
                              enabled: pickedScene != nil && state.remainingBudget > 0,
                              loading: generating) {
                    guard let key = pickedScene else { return }
                    Task { await generate(scene: key) }
                }
                Text(L("result_cost_line", state.remainingBudget))
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
            }
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

    private var generateTitle: String {
        guard let key = pickedScene, let scene = state.scene(for: key) else {
            return L("result_generate_pick")
        }
        return L("result_generate_scene", scene.title)
    }

    private var title: String {
        state.remainingBudget == 0 && state.usedFromPackage > 0
            ? L("result_all_done_title")
            : L("result_pick_scene_title")
    }

    private var subtitle: String {
        L("result_subtitle_progress", state.usedFromPackage,
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
            state.updateRemaining(response.photosRemaining)
        } catch let apiError as APIError {
            // 402 и 429 сервер отдаёт кодами, а не текстом: показываем причину,
            // а не общую «ошибка генерации».
            error = apiError.errorDescription
        } catch {
            self.error = L("result_error_generation")
        }
    }
}
