import SwiftUI

/// Одно селфи плюс необязательные рост и вес — их сервер подставляет в промпт.
struct UploadView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    @State private var showPicker = false
    @State private var height = ""
    @State private var weight = ""

    var body: some View {
        ScreenScaffold(title: L("upload_title"), subtitle: L("upload_subtitle")) {
            Button {
                showPicker = true
            } label: {
                ZStack {
                    RoundedRectangle(cornerRadius: 14)
                        .fill(Palette.fill)
                        .aspectRatio(1, contentMode: .fit)
                    if let data = state.photoData, let image = UIImage(data: data) {
                        Image(uiImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    } else {
                        VStack(spacing: 10) {
                            Image(systemName: "person.crop.square.badge.camera")
                                .font(.system(size: 40))
                                .foregroundStyle(.secondary)
                            Text(L("upload_pick")).font(.inter(16)).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .buttonStyle(.plain)

            if state.photoData != nil {
                Button(L("upload_replace")) { showPicker = true }
                    .buttonStyle(.bordered)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(L("upload_body_hint")).font(.inter(13)).foregroundStyle(.secondary)
                HStack(spacing: 12) {
                    LabeledField(title: L("upload_height_label"), text: $height)
                    LabeledField(title: L("upload_weight_label"), text: $weight)
                }
            }
            .padding(.top, 8)
        } bottom: {
            PrimaryButton(title: L("upload_next"), enabled: state.photoData != nil) {
                state.heightCm = Int(height)
                state.weightKg = Int(weight)
                path.append(.result)
            }
        }
        .sheet(isPresented: $showPicker) {
            PhotoPicker(data: Binding(get: { state.photoData },
                                      set: { state.photoData = $0 }))
        }
    }
}

private struct LabeledField: View {
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
