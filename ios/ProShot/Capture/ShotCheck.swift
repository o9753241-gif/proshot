import AVFoundation
import CoreImage
import UIKit
import Vision

/// Что не так с кадром.
///
/// Это основное отличие ProShot от простой загрузки файла: снимок проверяется
/// на устройстве до того, как за него спишут фото из пакета. Человек видит
/// живую подсказку и жмёт затвор только тогда, когда кадр годный.
enum ShotProblem: String {
    case noFace, manyFaces, tooFar, tooClose, offCenter, turned, tilted, dark, bright, blurry

    /// Подсказка человеку. Ключи выписаны вручную, а не собраны из rawValue:
    /// так их видит проверялка локализации (check_l10n.py).
    var hint: String {
        switch self {
        case .noFace:     return L("shot_no_face")
        case .manyFaces:  return L("shot_many_faces")
        case .tooFar:     return L("shot_too_far")
        case .tooClose:   return L("shot_too_close")
        case .offCenter:  return L("shot_off_center")
        case .turned:     return L("shot_turned")
        case .tilted:     return L("shot_tilted")
        case .dark:       return L("shot_dark")
        case .bright:     return L("shot_bright")
        case .blurry:     return L("shot_blurry")
        }
    }

    /// Во сколько обходится баллу качества. Балл нужен, чтобы из трёх
    /// снятых кадров выбрать лучший.
    var penalty: Double {
        switch self {
        case .noFace, .manyFaces:            return 1.0
        case .tooFar, .tooClose, .blurry:    return 0.35
        case .turned, .dark:                 return 0.25
        case .tilted, .offCenter, .bright:   return 0.15
        }
    }
}

struct ShotQuality {
    let problems: [ShotProblem]
    /// 0…1.
    let score: Double
    /// Дисперсия лапласиана по области лица. Тай-брейк между двумя
    /// одинаково годными кадрами.
    let sharpness: Double
    /// Лицо в координатах изображения: 0…1, начало сверху слева.
    let faceRect: CGRect?

    var isGood: Bool { problems.isEmpty }
    var hint: String { problems.first?.hint ?? L("shot_ok") }

    static let none = ShotQuality(problems: [.noFace], score: 0, sharpness: 0, faceRect: nil)
}

enum ShotCheck {

    /// Ниже этого лицо считается мелким: генератор по такому кадру теряет черты.
    private static let minFaceHeight = 0.24
    private static let maxFaceHeight = 0.72
    /// Дисперсия лапласиана ниже этого — кадр смазан. Порог намеренно низкий:
    /// ложное «смазано» заблокировало бы затвор на нормальном снимке.
    private static let minSharpness = 25.0

    private static let ciContext = CIContext(options: [.useSoftwareRenderer: false])

    // MARK: - Входные точки

    /// Живой кадр с камеры. Буфер приходит уже развёрнутым в портрет
    /// (ориентация выставлена на соединении), поэтому Vision получает `.up`.
    static func analyze(pixelBuffer: CVPixelBuffer) -> ShotQuality {
        analyze(image: CIImage(cvPixelBuffer: pixelBuffer),
                handler: VNImageRequestHandler(cvPixelBuffer: pixelBuffer,
                                               orientation: .up,
                                               options: [:]))
    }

    /// Готовый снимок: свой же кадр после затвора или картинка из галереи.
    static func analyze(uiImage: UIImage) -> ShotQuality {
        guard let cg = uiImage.normalizedUp().cgImage else { return .none }
        return analyze(image: CIImage(cgImage: cg),
                       handler: VNImageRequestHandler(cgImage: cg,
                                                      orientation: .up,
                                                      options: [:]))
    }

    // MARK: - Разбор

    private static func analyze(image: CIImage, handler: VNImageRequestHandler) -> ShotQuality {
        let request = VNDetectFaceRectanglesRequest()
        // Третья ревизия отдаёт ещё и углы поворота головы — без них
        // «повернитесь к камере» проверить нечем.
        request.revision = VNDetectFaceRectanglesRequestRevision3
        do {
            try handler.perform([request])
        } catch {
            return .none
        }

        let faces = request.results ?? []
        guard let face = faces.max(by: { $0.boundingBox.height < $1.boundingBox.height }) else {
            return .none
        }

        var problems: [ShotProblem] = []
        if faces.count > 1 { problems.append(.manyFaces) }

        // Vision считает от нижнего левого угла, интерфейс — от верхнего.
        let box = face.boundingBox
        let rect = CGRect(x: box.minX, y: 1 - box.maxY, width: box.width, height: box.height)

        if box.height < minFaceHeight {
            problems.append(.tooFar)
        } else if box.height > maxFaceHeight {
            problems.append(.tooClose)
        }

        // 0.44 по вертикали, а не 0.5: на портрете лицо стоит чуть выше центра.
        if abs(rect.midX - 0.5) > 0.16 || abs(rect.midY - 0.44) > 0.18 {
            problems.append(.offCenter)
        }

        if abs(degrees(face.yaw)) > 18 || abs(degrees(face.pitch)) > 20 {
            problems.append(.turned)
        }
        if abs(degrees(face.roll)) > 12 {
            problems.append(.tilted)
        }

        var sharpness = 0.0
        if let stats = stats(of: image, faceBox: box) {
            sharpness = stats.sharpness
            if stats.mean < 0.22 {
                problems.append(.dark)
            } else if stats.mean > 0.88 {
                problems.append(.bright)
            }
            if stats.sharpness < minSharpness { problems.append(.blurry) }
        }

        let penalty = problems.reduce(0) { $0 + $1.penalty }
        return ShotQuality(problems: problems,
                           score: max(0, 1 - penalty),
                           sharpness: sharpness,
                           faceRect: rect)
    }

    // MARK: - Яркость и резкость

    /// Считаем только по лицу: тёмный фон за окном не должен объявлять
    /// нормально освещённого человека «слишком темно».
    private static func stats(of image: CIImage, faceBox: CGRect) -> (mean: Double, sharpness: Double)? {
        let extent = image.extent
        guard extent.width > 1, extent.height > 1 else { return nil }

        let rect = CGRect(x: extent.minX + faceBox.minX * extent.width,
                          y: extent.minY + faceBox.minY * extent.height,
                          width: faceBox.width * extent.width,
                          height: faceBox.height * extent.height).integral
        let cropped = image.cropped(to: rect)
        guard !cropped.extent.isEmpty else { return nil }

        // 128 пикселей по длинной стороне: и разбор дешёвый, и мера резкости
        // остаётся осмысленной.
        let scale = 128 / max(cropped.extent.width, cropped.extent.height)
        let small = cropped.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        guard let cg = ciContext.createCGImage(small, from: small.extent) else { return nil }
        return grayStats(cg)
    }

    private static func grayStats(_ cg: CGImage) -> (mean: Double, sharpness: Double)? {
        let width = cg.width
        let height = cg.height
        guard width > 8, height > 8 else { return nil }

        var pixels = [UInt8](repeating: 0, count: width * height)
        let drawn = pixels.withUnsafeMutableBytes { raw -> Bool in
            guard let base = raw.baseAddress,
                  let context = CGContext(data: base,
                                          width: width,
                                          height: height,
                                          bitsPerComponent: 8,
                                          bytesPerRow: width,
                                          space: CGColorSpaceCreateDeviceGray(),
                                          bitmapInfo: CGImageAlphaInfo.none.rawValue)
            else { return false }
            context.draw(cg, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard drawn else { return nil }

        var sum = 0.0
        for value in pixels { sum += Double(value) }
        let mean = sum / Double(width * height) / 255

        // Дисперсия лапласиана — обычная мера резкости: у смазанного кадра
        // перепадов между соседними пикселями почти нет.
        var laplacianSum = 0.0
        var laplacianSquares = 0.0
        var count = 0
        for y in 1..<(height - 1) {
            for x in 1..<(width - 1) {
                let i = y * width + x
                let value = 4 * Double(pixels[i])
                    - Double(pixels[i - 1]) - Double(pixels[i + 1])
                    - Double(pixels[i - width]) - Double(pixels[i + width])
                laplacianSum += value
                laplacianSquares += value * value
                count += 1
            }
        }
        guard count > 0 else { return nil }
        let average = laplacianSum / Double(count)
        return (mean, laplacianSquares / Double(count) - average * average)
    }

    private static func degrees(_ radians: NSNumber?) -> Double {
        guard let radians else { return 0 }
        return radians.doubleValue * 180 / .pi
    }
}

extension UIImage {
    /// Перерисовывает картинку так, чтобы ориентация стала `.up`.
    /// Vision работает с CGImage и о повороте из UIImage не знает.
    func normalizedUp() -> UIImage {
        guard imageOrientation != .up else { return self }
        return UIGraphicsImageRenderer(size: size).image { _ in
            draw(in: CGRect(origin: .zero, size: size))
        }
    }
}

/// Снятый кадр вместе с его оценкой.
///
/// Оценку храним рядом с картинкой: по ней потом выбирается лучший из трёх
/// кадров, и пересчитывать разбор второй раз не приходится.
struct CapturedShot: Identifiable {
    let id = UUID()
    let data: Data
    let quality: ShotQuality
}
