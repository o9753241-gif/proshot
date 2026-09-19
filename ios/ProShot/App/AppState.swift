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
    @Published var industries: [IndustryDTO] = []

    // Выбор пользователя
    @Published var selectedPackage: PackageDTO?
    @Published var selectedScenes: [String] = []
    /// Отрасль: по ней каталог показывает свою подборку сцен.
    @Published var industry: String?
    /// Три снятых кадра. Слот пустой, пока кадр не снят; порядок совпадает
    /// с порядком подсказок на экране съёмки.
    @Published var shots: [CapturedShot?] = Array(repeating: nil, count: AppState.shotCount)
    @Published var heightCm: Int?
    @Published var weightKg: Int?

    /// Сколько кадров снимаем в проходе.
    static let shotCount = 3

    // Результаты генерации: сцена → адреса готовых фото
    @Published var results: [String: [URL]] = [:]

    /// Снимок, который сейчас раскладывают по форматам на экране кадрировок.
    @Published var cropSource: URL?

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
            async let industries = ProShotAPI.shared.industries()
            async let styles = ProShotAPI.shared.styles(maxTier: 3)
            self.packages = try await packages
            self.industries = try await industries
            self.styles = try await styles
        } catch {
            errorMessage = (error as? APIError)?.errorDescription ?? L("error_network")
        }
    }

    /// Переключение подборки. Сцены перезапрашиваются с сервера: фильтрация
    /// живёт там, и состав подборки можно поправить без новой версии приложения.
    func selectIndustry(_ key: String?) async {
        industry = key
        selectedScenes = []
        isLoading = true
        defer { isLoading = false }
        do {
            styles = try await ProShotAPI.shared.styles(maxTier: 3, industry: key)
            errorMessage = nil
        } catch {
            errorMessage = (error as? APIError)?.errorDescription ?? L("error_network")
        }
    }

    /// Название выбранной подборки для подзаголовков.
    var industryTitle: String {
        guard let industry else { return L("industry_all") }
        return industries.first { $0.key == industry }?.title ?? L("industry_all")
    }

    // MARK: - Производные величины

    /// Сцены, доступные выбранному тарифу. Каталог отдаёт все, но пакет
    /// ограничивает глубину: scenes_pool — сколько сцен ему открыто.
    var availableScenes: [StyleDTO] {
        guard let pkg = selectedPackage else { return styles }
        return Array(styles.prefix(pkg.scenesPool))
    }

    var capturedCount: Int {
        shots.compactMap { $0 }.count
    }

    /// Кадр, который уходит в генерацию: самый чистый по разбору Vision.
    /// При равных оценках выигрывает более резкий.
    var bestShot: CapturedShot? {
        shots.compactMap { $0 }.max {
            ($0.quality.score, $0.quality.sharpness) < ($1.quality.score, $1.quality.sharpness)
        }
    }

    var photoData: Data? { bestShot?.data }

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
        industry = nil
        shots = Array(repeating: nil, count: AppState.shotCount)
    }
}
