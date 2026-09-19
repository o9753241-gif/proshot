import SwiftUI
import UIKit

/// Форматы, в которые готовый портрет пересобирается прямо на телефоне.
///
/// Генератор отдаёт квадрат. Для профиля, резюме, обложки созвона и сторис
/// нужны разные пропорции и разная крупность лица — и подрезать их вручную
/// человеку приходится в стороннем редакторе. ProShot делает это сам.
enum CropFormat: String, CaseIterable, Identifiable {
    case avatar, cv, cover, story

    var id: String { rawValue }
    var title: String {
        switch self {
        case .avatar: return L("crop_avatar")
        case .cv:     return L("crop_cv")
        case .cover:  return L("crop_cover")
        case .story:  return L("crop_story")
        }
    }

    var note: String {
        switch self {
        case .avatar: return L("crop_avatar_note")
        case .cv:     return L("crop_cv_note")
        case .cover:  return L("crop_cover_note")
        case .story:  return L("crop_story_note")
        }
    }

    /// Размер готового файла в пикселях.
    var size: CGSize {
        switch self {
        case .avatar: return CGSize(width: 1024, height: 1024)
        case .cv:     return CGSize(width: 1080, height: 1440)
        case .cover:  return CGSize(width: 1920, height: 1080)
        case .story:  return CGSize(width: 1080, height: 1920)
        }
    }

    /// Какую долю высоты кадра должно занимать лицо.
    var faceHeight: CGFloat {
        switch self {
        case .avatar: return 0.46
        case .cv:     return 0.32
        case .cover:  return 0.40
        case .story:  return 0.24
        }
    }

    /// Где по вертикали стоит центр лица. Строго по середине лицо ставить
    /// нельзя: над головой нужен воздух, иначе кадр выглядит тесным.
    var faceCenterY: CGFloat {
        switch self {
        case .avatar: return 0.44
        case .cv:     return 0.36
        case .cover:  return 0.44
        case .story:  return 0.34
        }
    }
}

enum CropKit {

    /// Пересобирает снимок под формат, ориентируясь на положение лица.
    ///
    /// Если после масштабирования картинка не закрывает весь кадр — а так
    /// и бывает с широкой обложкой из квадрата, — пустое место заполняется
    /// размытой копией самого снимка, а не чёрной рамкой.
    static func render(_ source: UIImage, as format: CropFormat) -> UIImage {
        let image = source.normalizedUp()
        let target = format.size
        let sourceSize = image.size
        guard sourceSize.width > 0, sourceSize.height > 0 else { return image }

        let face = ShotCheck.analyze(uiImage: image).faceRect
        let background = blurred(image)

        return UIGraphicsImageRenderer(size: target).image { context in
            // Подложка: снимок, растянутый до заполнения кадра и размытый.
            draw(background, filling: target)

            let rect: CGRect
            if let face, face.height > 0.02 {
                let faceBox = CGRect(x: face.minX * sourceSize.width,
                                     y: face.minY * sourceSize.height,
                                     width: face.width * sourceSize.width,
                                     height: face.height * sourceSize.height)
                // Масштаб задаёт лицо: оно должно занять заданную долю высоты.
                let scale = (format.faceHeight * target.height) / faceBox.height
                let size = CGSize(width: sourceSize.width * scale,
                                  height: sourceSize.height * scale)
                let origin = CGPoint(x: target.width * 0.5 - faceBox.midX * scale,
                                     y: target.height * format.faceCenterY - faceBox.midY * scale)
                rect = CGRect(origin: origin, size: size)
            } else {
                // Лицо не нашлось — обычное заполнение кадра по центру.
                rect = fillRect(for: sourceSize, in: target)
            }

            context.cgContext.interpolationQuality = .high
            image.draw(in: rect)
        }
    }

    /// Все форматы разом. Разбор лица идёт заново на каждый — это доли
    /// секунды, зато функция остаётся независимой от порядка вызовов.
    static func renderAll(_ source: UIImage) -> [(format: CropFormat, image: UIImage)] {
        CropFormat.allCases.map { ($0, render(source, as: $0)) }
    }

    // MARK: - Внутреннее

    /// Размытие без CoreImage: уменьшаем до сорока пикселей и растягиваем
    /// обратно с интерполяцией. Дёшево, и результат от гауссова не отличить.
    private static func blurred(_ image: UIImage) -> UIImage {
        let side: CGFloat = 40
        let scale = side / max(image.size.width, image.size.height)
        let small = CGSize(width: max(1, image.size.width * scale),
                           height: max(1, image.size.height * scale))
        return UIGraphicsImageRenderer(size: small).image { context in
            context.cgContext.interpolationQuality = .low
            image.draw(in: CGRect(origin: .zero, size: small))
        }
    }

    private static func draw(_ image: UIImage, filling target: CGSize) {
        image.draw(in: fillRect(for: image.size, in: target))
    }

    /// Прямоугольник, в котором картинка заполняет кадр целиком (aspect fill).
    private static func fillRect(for source: CGSize, in target: CGSize) -> CGRect {
        guard source.width > 0, source.height > 0 else {
            return CGRect(origin: .zero, size: target)
        }
        let scale = max(target.width / source.width, target.height / source.height)
        let size = CGSize(width: source.width * scale, height: source.height * scale)
        return CGRect(x: (target.width - size.width) / 2,
                      y: (target.height - size.height) / 2,
                      width: size.width,
                      height: size.height)
    }
}
