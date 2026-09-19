import SwiftUI

/// Готовый портрет, разложенный по рабочим форматам.
///
/// Всё считается на устройстве: снимок скачивается один раз, дальше только
/// местная пересборка. Сервер об этом экране не знает и лишних генераций
/// не тратится.
struct CropSetView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    @State private var crops: [CropItem] = []
    @State private var loading = true
    @State private var failed = false
    @State private var saving = false
    @State private var toast: String?

    var body: some View {
        ScreenScaffold(title: L("crops_title"), subtitle: L("crops_subtitle")) {
            if loading {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            } else if failed {
                ErrorBlock(message: L("crops_failed")) { Task { await build() } }
            } else {
                if let toast {
                    Text(toast).font(.inter(13)).foregroundStyle(.secondary)
                }
                ForEach(crops) { item in
                    CropCard(item: item) {
                        Task {
                            let ok = await PhotoSaver.save(image: item.image)
                            toast = ok ? L("result_saved_ok") : L("result_saved_fail")
                        }
                    }
                }
            }
        } bottom: {
            PrimaryButton(title: L("crops_save_all"),
                          enabled: !crops.isEmpty,
                          loading: saving) {
                Task { await saveAll() }
            }
        }
        .task { await build() }
    }

    private func build() async {
        loading = true
        failed = false
        defer { loading = false }

        guard let url = state.cropSource else {
            failed = true
            return
        }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else {
                failed = true
                return
            }
            // Пересборка четырёх форматов с разбором лица в каждом занимает
            // доли секунды, поэтому считаем на месте: уносить UIImage в
            // отдельную задачу ради этого не стоит.
            crops = CropKit.renderAll(image).map {
                CropItem(format: $0.format, image: $0.image)
            }
        } catch {
            failed = true
        }
    }

    private func saveAll() async {
        saving = true
        defer { saving = false }
        var saved = 0
        for item in crops {
            if await PhotoSaver.save(image: item.image) { saved += 1 }
        }
        toast = saved == crops.count
            ? L("crops_saved_all", saved)
            : L("crops_saved_some", saved, crops.count)
    }
}

struct CropItem: Identifiable {
    let format: CropFormat
    let image: UIImage

    var id: String { format.rawValue }
}

private struct CropCard: View {
    let item: CropItem
    let save: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Image(uiImage: item.image)
                .resizable()
                .aspectRatio(item.format.size.width / item.format.size.height,
                             contentMode: .fit)
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 12))

            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.format.title).font(.inter(16, .semibold))
                    Text(item.format.note).font(.inter(12)).foregroundStyle(.secondary)
                }
                Spacer()
                Text("\(Int(item.format.size.width))×\(Int(item.format.size.height))")
                    .font(.inter(11))
                    .foregroundStyle(.secondary)
            }

            HStack(spacing: 12) {
                Button(L("action_save"), action: save).buttonStyle(.bordered)
                ShareLink(item: Image(uiImage: item.image),
                          preview: SharePreview(item.format.title,
                                                image: Image(uiImage: item.image))) {
                    Text(L("action_share"))
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
    }
}
