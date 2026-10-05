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

    /// Оплаченный пакет с непотраченными фото. Источник правды — сервер:
    /// без этого после выхода на главный или перезапуска приложения оплаченный
    /// остаток был недоступен, и экран предлагал купить тариф заново.
    @Published var activePurchase: PurchaseDTO?

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
            await refreshPurchase()
        } catch {
            errorMessage = (error as? APIError)?.errorDescription ?? L("error_network")
        }
    }

    /// Выбор подборки. Каталог при этом не урезается: подборка лишь поднимает
    /// уместные сцены наверх. Прятать половину витрины за выбором профессии —
    /// значит показывать двенадцать карточек вместо полусотни.
    func selectIndustry(_ key: String?) {
        industry = key
        selectedScenes = []
    }

    /// Название выбранной подборки для подзаголовков.
    var industryTitle: String {
        guard let industry else { return L("industry_all") }
        return industries.first { $0.key == industry }?.title ?? L("industry_all")
    }

    // MARK: - Производные величины

    /// Сцены, доступные выбранному тарифу.
    ///
    /// Сейчас каталог открыт целиком в любом пакете, и max_tier у всех троих
    /// равен трём. Отбор оставлен: граница живёт на сервере, и если тиры
    /// когда-нибудь вернут, приложение подхватит это без новой версии.
    var availableScenes: [StyleDTO] {
        guard let pkg = selectedPackage else { return styles }
        return styles.filter { $0.tier <= pkg.maxTier }
    }

    /// Ключи сцен выбранной подборки.
    private var industryKeys: [String] {
        guard let industry else { return [] }
        return industries.first { $0.key == industry }?.sceneKeys ?? []
    }

    /// Сцены подборки — те, что уместны в работе человека.
    func recommended(from scenes: [StyleDTO]) -> [StyleDTO] {
        let keys = Set(industryKeys)
        guard !keys.isEmpty else { return [] }
        return scenes.filter { keys.contains($0.key) }
    }

    /// Всё остальное из каталога. Ничего не скрыто, просто ниже.
    func others(from scenes: [StyleDTO]) -> [StyleDTO] {
        let keys = Set(industryKeys)
        guard !keys.isEmpty else { return scenes }
        return scenes.filter { !keys.contains($0.key) }
    }

    /// Порядок для экранов, где список один: сначала подборка, потом остальные.
    var orderedScenes: [StyleDTO] {
        recommended(from: availableScenes) + others(from: availableScenes)
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

    /// Сколько фото из пакета ещё не израсходовано. Берётся с сервера,
    /// счёт по локальным результатам — только запасной вариант.
    var remainingBudget: Int {
        if let activePurchase { return activePurchase.photosRemaining }
        return max((selectedPackage?.totalPhotos ?? 0) - totalGenerated, 0)
    }

    /// Сколько фото из пакета уже израсходовано (в том числе до перезапуска).
    var usedFromPackage: Int {
        max((selectedPackage?.totalPhotos ?? 0) - remainingBudget, 0)
    }

    /// Пакет активной покупки — для подписи на главном экране.
    var activePackage: PackageDTO? {
        guard let sku = activePurchase?.sku else { return nil }
        return packages.first { $0.sku == sku }
    }

    /// Последняя оплаченная покупка с остатком, как её выбирает сервер.
    func refreshPurchase() async {
        guard let list = try? await ProShotAPI.shared.purchases() else { return }
        activePurchase = list.filter { $0.isActive }.max { $0.id < $1.id }
    }

    /// Остаток после генерации: сервер присылает его в ответе.
    func updateRemaining(_ remaining: Int?) {
        guard let remaining, let p = activePurchase else { return }
        activePurchase = remaining > 0
            ? PurchaseDTO(id: p.id, sku: p.sku, status: p.status,
                          scenesSelected: p.scenesSelected, photosRemaining: remaining)
            : nil
    }

    /// Возвращает выбор оплаченного пакета: тариф и сцены, указанные при оплате.
    /// false — если пакета нет или его тарифа нет в списке с сервера.
    func resumePurchase() -> Bool {
        guard let p = activePurchase, let pkg = activePackage else { return false }
        selectedPackage = pkg
        selectedScenes = p.scenesSelected
        return true
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
