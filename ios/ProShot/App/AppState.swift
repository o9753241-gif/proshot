import Foundation
import SwiftUI

/// Состояние прохода по экранам: тариф, сцены, фото, результаты.
///
/// Один объект на всё приложение — как PurchaseFlowState в Android-версии.
/// Экраны его читают и меняют, сеть живёт в ProShotAPI.
@MainActor
@Observable
final class AppState {

    // Данные с сервера
    var packages: [PackageDTO] = []
    var styles: [StyleDTO] = []

    // Выбор пользователя
    var selectedPackage: PackageDTO?
    var selectedScenes: [String] = []
    var photoData: Data?
    var heightCm: Int?
    var weightKg: Int?

    // Результаты генерации: сцена → адреса готовых фото
    var results: [String: [URL]] = [:]

    var isLoading = false
    var errorMessage: String?

    /// Показывать ли онбординг. Один раз на установку, как на Android.
    var needsOnboarding: Bool {
        get { !UserDefaults.standard.bool(forKey: "proshot.onboarding.done") }
        set { UserDefaults.standard.set(!newValue, forKey: "proshot.onboarding.done") }
    }

    // MARK: - Загрузка

    func bootstrap() async {
        isLoading = true
        defer { isLoading = false }
        do {
            _ = try await ProShotAPI.shared.registerDevice()
            async let packages = ProShotAPI.shared.packages()
            async let styles = ProShotAPI.shared.styles(maxTier: 3)
            self.packages = try await packages
            self.styles = try await styles
        } catch {
            errorMessage = (error as? APIError)?.errorDescription ?? L("error_network")
        }
    }

    // MARK: - Производные величины

    /// Сцены, доступные выбранному тарифу. Каталог отдаёт все, но пакет
    /// ограничивает глубину: scenes_pool — сколько сцен ему открыто.
    var availableScenes: [StyleDTO] {
        guard let pkg = selectedPackage else { return styles }
        return Array(styles.prefix(pkg.scenesPool))
    }

    var totalGenerated: Int {
        results.values.reduce(0) { $0 + $1.count }
    }

    /// Сколько фото из пакета ещё не израсходовано.
    var remainingBudget: Int {
        max((selectedPackage?.totalPhotos ?? 0) - totalGenerated, 0)
    }

    /// Примерно столько фото придётся на каждую выбранную сцену.
    var photosPerScene: Int {
        guard let pkg = selectedPackage, !selectedScenes.isEmpty else { return 0 }
        return pkg.totalPhotos / selectedScenes.count
    }

    func scene(for key: String) -> StyleDTO? {
        styles.first { $0.key == key }
    }

    func toggleScene(_ key: String) {
        guard let pkg = selectedPackage else { return }
        if let index = selectedScenes.firstIndex(of: key) {
            selectedScenes.remove(at: index)
        } else if selectedScenes.count < pkg.maxScenes {
            selectedScenes.append(key)
        }
    }

    /// Сбрасывает всё, кроме уже готовых фото: они остаются в галерее.
    func startOver() {
        selectedPackage = nil
        selectedScenes = []
        photoData = nil
    }
}
