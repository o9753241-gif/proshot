import Foundation
import SwiftUI

/// Состояние прохода по экранам: тариф, сцены, фото, результаты.
///
/// Один объект на всё приложение — как PurchaseFlowState в Android-версии.
/// Экраны его читают и меняют, сеть живёт в ProShotAPI.
@MainActor
/// Наблюдение через ObservableObject, а не @Observable: последний доступен
/// только с iOS 17 и поднимал бы минимальную версию системы. Приложение
/// должно ставиться и на iOS 16.
final class AppState: ObservableObject {

    // Данные с сервера
    @Published var packages: [PackageDTO] = []
    @Published var styles: [StyleDTO] = []

    // Выбор пользователя
    @Published var selectedPackage: PackageDTO?
    @Published var selectedScenes: [String] = []
    @Published var photoData: Data?
    @Published var heightCm: Int?
    @Published var weightKg: Int?

    // Результаты генерации: сцена → адреса готовых фото
    @Published var results: [String: [URL]] = [:]

    @Published var isLoading = false
    @Published var errorMessage: String?

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
