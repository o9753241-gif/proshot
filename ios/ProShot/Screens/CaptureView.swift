import SwiftUI

/// Съёмка трёх кадров с проверкой прямо в приложении.
///
/// Снимок проверяется до того, как за него спишут фото из пакета: лицо в кадре,
/// нужного размера, по центру, не повёрнуто, освещено и не смазано. Затвор
/// открывается только на годном кадре, а подсказка под видоискателем меняется
/// на лету. Три ракурса нужны, чтобы генератор видел лицо с разных сторон —
/// в работу уходит лучший из них.
struct CaptureView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState
    @StateObject private var camera = CameraSession()

    @State private var slot = 0
    @State private var busy = false
    @State private var showPicker = false
    @State private var pickedImage: UIImage?
    @State private var note: String?
    @State private var height = ""
    @State private var weight = ""

    private let steps: [(title: String, body: String)] = [
        (L("capture_step1_title"), L("capture_step1_body")),
        (L("capture_step2_title"), L("capture_step2_body")),
        (L("capture_step3_title"), L("capture_step3_body")),
    ]

    var body: some View {
        ScreenScaffold(title: L("capture_title"),
                       subtitle: L("capture_subtitle", slot + 1, AppState.shotCount)) {
            VStack(alignment: .leading, spacing: 6) {
                Text(steps[slot].title).font(.inter(18, .semibold))
                Text(steps[slot].body)
                    .font(.inter(13))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            viewfinder

            if camera.unavailable || camera.accessDenied {
                Text(camera.accessDenied ? L("capture_denied") : L("capture_no_camera"))
                    .font(.inter(13))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Button(L("capture_from_library")) { showPicker = true }
                    .buttonStyle(.bordered)
            } else {
                shutter
                Button(L("capture_from_library")) { showPicker = true }
                    .buttonStyle(.borderless)
                    .font(.inter(13))
            }

            if let note {
                Text(note).font(.inter(13)).foregroundStyle(.orange)
                    .fixedSize(horizontal: false, vertical: true)
            }

            strip

            bodyFields
        } bottom: {
            PrimaryButton(title: L("capture_next"), enabled: state.capturedCount > 0) {
                state.heightCm = Int(height)
                state.weightKg = Int(weight)
                path.append(.result)
            }
        }
        .onAppear { syncSlot(); camera.start() }
        .onDisappear { camera.stop() }
        .sheet(isPresented: $showPicker) {
            PhotoPicker(image: $pickedImage)
        }
        .onChange(of: pickedImage) { image in
            guard let image else { return }
            pickedImage = nil
            accept(image, fromLibrary: true)
        }
    }

    // MARK: - Видоискатель

    private var viewfinder: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18).fill(Palette.fill)

            if !camera.unavailable && !camera.accessDenied {
                CameraPreview(session: camera.session)
                    .clipShape(RoundedRectangle(cornerRadius: 18))
            } else {
                Image(systemName: "camera.fill")
                    .font(.system(size: 40))
                    .foregroundStyle(.secondary)
            }

            // Овал-ориентир: лицо должно его примерно заполнять.
            Ellipse()
                .strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [7, 6]))
                .foregroundColor(.white.opacity(0.75))
                .padding(.horizontal, 44)
                .padding(.vertical, 56)

            VStack {
                Spacer()
                Text(camera.quality.hint)
                    .font(.inter(13, .medium))
                    .multilineTextAlignment(.center)
                    .foregroundColor(.white)
                    .padding(.horizontal, 12).padding(.vertical, 7)
                    .background(Color.black.opacity(0.55), in: Capsule())
                    .padding(.bottom, 12)
            }
        }
        .aspectRatio(3.0 / 4.0, contentMode: .fit)
        .frame(maxWidth: .infinity)
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .strokeBorder(camera.quality.isGood ? Color.green : Color.clear, lineWidth: 3)
        }
    }

    private var shutter: some View {
        HStack {
            Spacer()
            Button {
                Task { await shoot() }
            } label: {
                ZStack {
                    Circle()
                        .strokeBorder(camera.quality.isGood ? Color.accentColor : Color.gray,
                                      lineWidth: 4)
                        .frame(width: 72, height: 72)
                    if busy {
                        ProgressView()
                    } else {
                        Circle()
                            .fill(camera.quality.isGood ? Color.accentColor : Color.gray.opacity(0.4))
                            .frame(width: 56, height: 56)
                    }
                }
            }
            .buttonStyle(.plain)
            .disabled(busy || !camera.quality.isGood)
            Spacer()
        }
    }

    // MARK: - Полоска снятых кадров

    private var strip: some View {
        HStack(spacing: 10) {
            ForEach(0..<AppState.shotCount, id: \.self) { index in
                Button {
                    slot = index
                    note = nil
                } label: {
                    ZStack {
                        RoundedRectangle(cornerRadius: 10).fill(Palette.fill)
                        if let shot = state.shots[index],
                           let image = UIImage(data: shot.data) {
                            Image(uiImage: image)
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                        } else {
                            Text("\(index + 1)")
                                .font(.inter(16, .semibold))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .aspectRatio(3.0 / 4.0, contentMode: .fit)
                    .overlay {
                        RoundedRectangle(cornerRadius: 10)
                            .strokeBorder(index == slot ? Color.accentColor : .clear, lineWidth: 2)
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var bodyFields: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(L("upload_body_hint"))
                .font(.inter(13))
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                NumberField(title: L("upload_height_label"), text: $height)
                NumberField(title: L("upload_weight_label"), text: $weight)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Действия

    /// Слот по умолчанию — первый ещё не снятый.
    private func syncSlot() {
        slot = state.shots.firstIndex(where: { $0 == nil }) ?? 0
    }

    private func shoot() async {
        busy = true
        defer { busy = false }
        guard let image = await camera.capture() else {
            note = L("capture_failed")
            return
        }
        accept(image, fromLibrary: false)
    }

    private func accept(_ image: UIImage, fromLibrary: Bool) {
        // Кадр из галереи мог не проходить проверок: там затвора нет и
        // остановить человека нечем. Берём, но честно говорим, что не так.
        let quality = ShotCheck.analyze(uiImage: image)
        guard let data = image.resized(maxSide: 2048).jpegData(compressionQuality: 0.9) else {
            note = L("capture_failed")
            return
        }
        state.shots[slot] = CapturedShot(data: data, quality: quality)
        note = (fromLibrary && !quality.isGood) ? L("capture_library_warning", quality.hint) : nil

        if let next = state.shots.firstIndex(where: { $0 == nil }) {
            slot = next
        }
    }
}

private struct NumberField: View {
    let title: String
    @Binding var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.inter(12)).foregroundStyle(.secondary)
            TextField("", text: $text)
                .keyboardType(.numberPad)
                .textFieldStyle(.roundedBorder)
        }
    }
}
