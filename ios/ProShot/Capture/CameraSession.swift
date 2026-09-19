import AVFoundation
import SwiftUI
import UIKit

/// Живая камера с разбором кадра.
///
/// Класс намеренно НЕ помечен `@MainActor`: методы делегатов AVFoundation
/// приходят с фоновых очередей, и изоляция актора с ними не сходится.
/// Поэтому изоляция ручная — всё, что читает интерфейс, пишется через
/// `publish(_:)`, то есть с главного потока.
final class CameraSession: NSObject, ObservableObject {

    /// Оценка последнего разобранного кадра. По ней живёт подсказка и затвор.
    @Published private(set) var quality: ShotQuality = .none
    /// Камеры нет вовсе — симулятор или устройство без фронталки.
    @Published private(set) var unavailable = false
    /// Доступ к камере запрещён в настройках.
    @Published private(set) var accessDenied = false

    let session = AVCaptureSession()

    private let photoOutput = AVCapturePhotoOutput()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let sessionQueue = DispatchQueue(label: "ai.proshot.camera.session")
    private let analysisQueue = DispatchQueue(label: "ai.proshot.camera.analysis")

    /// Разбираем не каждый кадр: четыре раза в секунду хватает, чтобы
    /// подсказка выглядела живой, и телефон при этом не греется.
    private let analysisInterval: TimeInterval = 0.25
    private var lastAnalysis = Date.distantPast
    private var analysing = false
    private var configured = false

    private var shotHandler: ((UIImage?) -> Void)?

    // MARK: - Жизненный цикл

    func start() {
        Task {
            let granted = await Self.requestAccess()
            guard granted else {
                publish { self.accessDenied = true }
                return
            }
            self.sessionQueue.async {
                self.configureIfNeeded()
                guard !self.session.isRunning else { return }
                self.session.startRunning()
            }
        }
    }

    func stop() {
        sessionQueue.async {
            guard self.session.isRunning else { return }
            self.session.stopRunning()
        }
    }

    private static func requestAccess() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: return true
        case .notDetermined: return await AVCaptureDevice.requestAccess(for: .video)
        default: return false
        }
    }

    private func configureIfNeeded() {
        guard !configured else { return }
        configured = true

        session.beginConfiguration()
        session.sessionPreset = .photo

        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera,
                                                   for: .video,
                                                   position: .front),
              let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input)
        else {
            session.commitConfiguration()
            publish { self.unavailable = true }
            return
        }
        session.addInput(input)

        if session.canAddOutput(photoOutput) { session.addOutput(photoOutput) }

        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
        videoOutput.setSampleBufferDelegate(self, queue: analysisQueue)
        if session.canAddOutput(videoOutput) { session.addOutput(videoOutput) }

        session.commitConfiguration()

        // Разворачиваем кадр в портрет прямо на соединении. Тогда и Vision,
        // и готовый снимок приходят уже в том виде, в каком человек их видел,
        // и возиться с матрицами ориентации не нужно нигде.
        for output in [videoOutput as AVCaptureOutput, photoOutput as AVCaptureOutput] {
            guard let connection = output.connection(with: .video) else { continue }
            if connection.isVideoOrientationSupported {
                connection.videoOrientation = .portrait
            }
            if connection.isVideoMirroringSupported {
                connection.automaticallyAdjustsVideoMirroring = false
                connection.isVideoMirrored = true
            }
        }
    }

    // MARK: - Затвор

    /// Делает снимок. Возвращает `nil`, если камера не ответила.
    func capture() async -> UIImage? {
        await withCheckedContinuation { continuation in
            var resumed = false
            let finish: (UIImage?) -> Void = { image in
                guard !resumed else { return }
                resumed = true
                continuation.resume(returning: image)
            }
            self.sessionQueue.async {
                guard self.session.isRunning else {
                    finish(nil)
                    return
                }
                self.shotHandler = finish
                let settings = AVCapturePhotoSettings(
                    format: [AVVideoCodecKey: AVVideoCodecType.jpeg]
                )
                self.photoOutput.capturePhoto(with: settings, delegate: self)
            }
        }
    }

    // MARK: - Внутреннее

    private func publish(_ change: @escaping () -> Void) {
        if Thread.isMainThread {
            change()
        } else {
            DispatchQueue.main.async(execute: change)
        }
    }
}

extension CameraSession: AVCaptureVideoDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        let now = Date()
        guard !analysing, now.timeIntervalSince(lastAnalysis) >= analysisInterval else { return }
        guard let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        analysing = true
        lastAnalysis = now
        let result = ShotCheck.analyze(pixelBuffer: buffer)
        analysing = false

        publish { self.quality = result }
    }
}

extension CameraSession: AVCapturePhotoCaptureDelegate {
    func photoOutput(_ output: AVCapturePhotoOutput,
                     didFinishProcessingPhoto photo: AVCapturePhoto,
                     error: Error?) {
        let handler = shotHandler
        shotHandler = nil
        guard error == nil,
              let data = photo.fileDataRepresentation(),
              let image = UIImage(data: data)
        else {
            handler?(nil)
            return
        }
        handler?(image.normalizedUp())
    }
}
