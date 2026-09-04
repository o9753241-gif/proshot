import SwiftUI
import PhotosUI
import Photos

/// Выбор фото через PHPicker.
///
/// PHPicker не требует разрешения на доступ к галерее вовсе: система сама
/// показывает выбор, а приложение получает только выбранный снимок. Поэтому в
/// Info.plist нет NSPhotoLibraryUsageDescription — и на ревью нечего объяснять.
struct PhotoPicker: UIViewControllerRepresentable {
    @Binding var data: Data?
    @Environment(\.dismiss) private var dismiss

    func makeUIViewController(context: Context) -> PHPickerViewController {
        var config = PHPickerConfiguration()
        config.filter = .images
        config.selectionLimit = 1
        let picker = PHPickerViewController(configuration: config)
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: PHPickerViewController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    final class Coordinator: NSObject, PHPickerViewControllerDelegate {
        private let parent: PhotoPicker
        init(_ parent: PhotoPicker) { self.parent = parent }

        func picker(_ picker: PHPickerViewController, didFinishPicking results: [PHPickerResult]) {
            defer { parent.dismiss() }
            guard let provider = results.first?.itemProvider,
                  provider.canLoadObject(ofClass: UIImage.self) else { return }

            provider.loadObject(ofClass: UIImage.self) { object, _ in
                guard let image = object as? UIImage else { return }
                // Ужимаем до 2048 по длинной стороне: дальше качество генерации
                // не растёт, а загрузка по мобильной сети заметно дольше.
                let jpeg = image.resized(maxSide: 2048).jpegData(compressionQuality: 0.9)
                Task { @MainActor in self.parent.data = jpeg }
            }
        }
    }
}

extension UIImage {
    func resized(maxSide: CGFloat) -> UIImage {
        let side = max(size.width, size.height)
        guard side > maxSide else { return self }
        let scale = maxSide / side
        let target = CGSize(width: size.width * scale, height: size.height * scale)
        return UIGraphicsImageRenderer(size: target).image { _ in
            draw(in: CGRect(origin: .zero, size: target))
        }
    }
}

/// Сохранение готового снимка в галерею телефона.
///
/// Просим только право на добавление: читать чужие фото приложению незачем,
/// и в манифесте приватности это отражено.
enum PhotoSaver {
    static func save(from url: URL) async -> Bool {
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data) else { return false }

            let status = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
            guard status == .authorized || status == .limited else { return false }

            try await PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAsset(from: image)
            }
            return true
        } catch {
            return false
        }
    }
}
