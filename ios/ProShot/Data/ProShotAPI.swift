import Foundation

/// Ошибки, о которых экранам нужно говорить по-разному.
enum APIError: LocalizedError {
    /// Пакет израсходован или покупки нет — сервер отвечает 402.
    case noPhotosLeft
    /// Достигнут потолок скорости, 429.
    case hourlyLimit
    case server(status: Int, detail: String)
    case network(Error)
    case decoding(Error)

    var errorDescription: String? {
        switch self {
        case .noPhotosLeft: return "Фото в пакете закончились."
        case .hourlyLimit:  return "Слишком много генераций за час. Попробуйте позже."
        case .server(_, let detail): return detail
        case .network: return "Нет связи с сервером."
        case .decoding: return "Сервер ответил неожиданно."
        }
    }
}

/// Клиент к FastAPI-бэкенду. Контракт тот же, что у Android-версии:
/// заголовки `X-Device-Id` и `Accept-Language` идут с каждым запросом.
actor ProShotAPI {
    static let shared = ProShotAPI()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(session: URLSession? = nil) {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        // Генерация идёт долго, поэтому ресурсу дано столько же, сколько
        // readTimeout в Android-клиенте.
        config.timeoutIntervalForResource = 120
        self.session = session ?? URLSession(configuration: config)

        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    // MARK: - Запросы

    func registerDevice() async throws -> AuthResponse {
        try await send(path: "/api/v1/auth/device",
                       method: "POST",
                       body: ["device_id": DeviceID.current])
    }

    func packages() async throws -> [PackageDTO] {
        try await send(path: "/api/v1/packages", method: "GET")
    }

    func industries() async throws -> [IndustryDTO] {
        try await send(path: "/api/v1/styles/industries", method: "GET")
    }

    func styles(maxTier: Int, industry: String? = nil) async throws -> [StyleDTO] {
        var path = "/api/v1/styles?max_tier=\(maxTier)"
        if let industry, !industry.isEmpty {
            path += "&industry=\(industry)"
        }
        return try await send(path: path, method: "GET")
    }

    func purchases() async throws -> [PurchaseDTO] {
        try await send(path: "/api/v1/billing/purchases", method: "GET")
    }

    /// Отдаёт подписанную транзакцию серверу. Фото начисляет он, а не клиент.
    func verifyPurchase(sku: String,
                        signedTransaction: String,
                        scenes: [String]) async throws -> PurchaseDTO {
        let body = VerifyPurchaseRequest(sku: sku,
                                         signedTransaction: signedTransaction,
                                         scenesSelected: scenes)
        return try await send(path: "/api/v1/billing/verify",
                              method: "POST",
                              encodable: body)
    }

    /// Генерация: фото уходит как multipart, вместе со сценой и профилем.
    func generate(sceneKey: String,
                  imageData: Data,
                  heightCm: Int?,
                  weightKg: Int?) async throws -> GenerateResponse {
        var request = base(path: "/api/v1/generation/generate", method: "POST")
        let boundary = "proshot.\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)",
                         forHTTPHeaderField: "Content-Type")

        var body = Data()
        func field(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\n")
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            body.append("\(value)\r\n")
        }
        field("scene_key", sceneKey)
        if let heightCm { field("height_cm", String(heightCm)) }
        if let weightKg { field("weight_kg", String(weightKg)) }

        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"image\"; filename=\"photo.jpg\"\r\n")
        body.append("Content-Type: image/jpeg\r\n\r\n")
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n")
        request.httpBody = body

        return try await perform(request)
    }

    // MARK: - Внутреннее

    private func base(path: String, method: String) -> URLRequest {
        // Именно склейка строк, а не appending(path:): тот кодирует "?" как %3F
        // и запрос со строкой параметров (styles?max_tier=3) уходил бы битым.
        let url = URL(string: Config.apiBaseURL.absoluteString + path) ?? Config.apiBaseURL
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue(DeviceID.current, forHTTPHeaderField: "X-Device-Id")
        request.setValue(Self.acceptLanguage, forHTTPHeaderField: "Accept-Language")
        return request
    }

    /// Тот же формат, что собирает Android-клиент: "ru-RU,ru;q=0.9,en;q=0.5".
    /// Сервер берёт из него первые две буквы и по ним выбирает язык и валюту.
    private static var acceptLanguage: String {
        let locale = Locale.current
        let tag = locale.identifier(.bcp47)
        let language = locale.language.languageCode?.identifier ?? "en"
        let fallback = language == "en" ? "" : ",en;q=0.5"
        return "\(tag),\(language);q=0.9\(fallback)"
    }

    private func send<T: Decodable>(path: String,
                                    method: String,
                                    body: [String: String]? = nil) async throws -> T {
        var request = base(path: path, method: method)
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        return try await perform(request)
    }

    private func send<T: Decodable, B: Encodable>(path: String,
                                                  method: String,
                                                  encodable: B) async throws -> T {
        var request = base(path: path, method: method)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(encodable)
        return try await perform(request)
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network(error)
        }

        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            // FastAPI кладёт причину в "detail" — и коды, и человеческие строки.
            let json = try? JSONSerialization.jsonObject(with: data)
            let detail = (json as? [String: Any])?["detail"] as? String ?? ""
            switch (status, detail) {
            case (402, _): throw APIError.noPhotosLeft
            case (429, _): throw APIError.hourlyLimit
            default: throw APIError.server(status: status, detail: detail)
            }
        }

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }
}

private extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) { append(data) }
    }
}
