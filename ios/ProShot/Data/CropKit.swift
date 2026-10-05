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
        case .avatar: return 0.38
        case .cv:     return 0.32
        case .cover:  return 0.40
        case .story:  return 0.24
        }
    }

    /// Где по вертикали стоит центр лица. Строго по середине лицо ставить
    /// нельзя: над головой нужен воздух, иначе кадр выглядит тесным.
    var faceCenterY: CGFloat {
        switch self {
        case .avatar: return 0.46
        case .cv:     return 0.36
        case .cover:  return 0.50
        case .story:  return 0.34
        }
    }
}

enum CropKit {

    /// Пересобирает снимок под формат, ориентируясь на положение лица.
    ///
    /// Снимок всегда закрывает кадр целиком. Раньше пустое место (обложка
    /// 16:9 и сторис 9:16 из квадрата) заполнялось «размытой» копией, а на деле
    /// растянутой картинкой в 40 пикселей: сверху и по бокам шли пиксельные
    /// полосы с резкой границей. Теперь масштаб не меньше, чем нужно для
    /// заполнения, а сдвиг ограничен так, чтобы края снимка не входили в кадр.
    static func render(_ source: UIImage, as format: CropFormat) -> UIImage {
        let image = source.normalizedUp()
        let target = format.size
        let sourceSize = image.size
        guard sourceSize.width > 0, sourceSize.height > 0 else { return image }

        let fillScale = max(target.width / sourceSize.width, target.height / sourceSize.height)
        var scale = fillScale
        var center = CGPoint(x: sourceSize.width / 2, y: sourceSize.height / 2)
        var anchorY = target.height * 0.5

        if let face = ShotCheck.analyze(uiImage: image).faceRect, face.height > 0.02 {
            let faceBox = CGRect(x: face.minX * sourceSize.width,
                                 y: face.minY * sourceSize.height,
                                 width: face.width * sourceSize.width,
                                 height: face.height * sourceSize.height)
            // Лицо должно занять заданную долю высоты, но не ценой пустых полей.
            scale = max(fillScale, (format.faceHeight * target.height) / faceBox.height)
            center = CGPoint(x: faceBox.midX, y: faceBox.midY)
            anchorY = target.height * format.faceCenterY
        }

        let size = CGSize(width: sourceSize.width * scale, height: sourceSize.height * scale)
        var origin = CGPoint(x: target.width * 0.5 - center.x * scale,
                             y: anchorY - center.y * scale)
        // Края снимка не заходят внутрь кадра.
        origin.x = min(0, max(target.width - size.width, origin.x))
        origin.y = min(0, max(target.height - size.height, origin.y))

        let rendererFormat = UIGraphicsImageRendererFormat()
        // Ровно столько пикселей, сколько написано у формата (1920×1080 и т. д.),
        // а не вдвое-втрое больше по масштабу экрана.
        rendererFormat.scale = 1
        rendererFormat.opaque = true
        return UIGraphicsImageRenderer(size: target, format: rendererFormat).image { context in
            context.cgContext.interpolationQuality = .high
            image.draw(in: CGRect(origin: origin, size: size))
        }
    }

    /// Все форматы разом. Разбор лица идёт заново на каждый — это доли
    /// секунды, зато функция остаётся независимой от порядка вызовов.
    static func renderAll(_ source: UIImage) -> [(format: CropFormat, image: UIImage)] {
        CropFormat.allCases.map { ($0, render(source, as: $0)) }
    }
}
