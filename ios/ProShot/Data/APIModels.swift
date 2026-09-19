import Foundation

// Модели повторяют то, что реально отдаёт сервер (app/schemas.py).
// Имена полей в JSON — snake_case, поэтому декодер настроен на конвертацию,
// а не на ручные CodingKeys в каждой структуре.

struct AuthResponse: Decodable {
    let token: String
    let userId: Int
}

struct PackageDTO: Decodable, Identifiable, Hashable {
    let sku: String
    let title: String
    /// Сколько сцен доступно в каталоге для этого пакета.
    let scenesPool: Int
    /// Самый высокий тир сцен, открытый этим пакетом. Считает сервер: граница
    /// зависит от состава каталога, а он там и живёт.
    let maxTier: Int
    /// Верхняя граница выбора. Сервер вернёт 400, если прислать больше.
    let maxScenes: Int
    let totalPhotos: Int
    let priceRub: Int
    /// Готовая строка с сервера: "990 ₽" | "$9.99" | "€9,99".
    /// На пейволле показываем цену из StoreKit — она в валюте витрины
    /// пользователя и всегда совпадает с тем, что спишет Apple.
    let priceDisplay: String
    let currency: String

    var id: String { sku }
}

/// Отраслевая подборка сцен. Каталог из полусотни сцен целиком человеку
/// не нужен — нужны те, что уместны в его работе.
struct IndustryDTO: Decodable, Identifiable, Hashable {
    let key: String
    let title: String
    let sceneCount: Int
    let previewUrl: String

    var id: String { key }
}

struct StyleDTO: Decodable, Identifiable, Hashable {
    let key: String
    let title: String
    let previewUrl: String
    let tier: Int

    var id: String { key }
}

struct PurchaseDTO: Decodable, Identifiable, Hashable {
    let id: Int
    let sku: String
    /// "paid" | "refunded"
    let status: String
    let scenesSelected: [String]
    let photosRemaining: Int

    var isActive: Bool { status == "paid" && photosRemaining > 0 }
}

struct GenerateResponse: Decodable {
    let sceneKey: String
    let imageUrl: String
    let photosRemaining: Int?
}

/// Тело запроса на начисление пакета. `provider` фиксирован: этот клиент
/// разговаривает только с App Store.
struct VerifyPurchaseRequest: Encodable {
    let sku: String
    let provider = "app_store"
    let signedTransaction: String
    let scenesSelected: [String]
}
