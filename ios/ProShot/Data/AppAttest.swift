import Foundation
import CryptoKit
import DeviceCheck

/// Доказательство подлинности приложения — App Attest — и токен устройства.
/// Перенесено из Starshot iOS без изменений логики.
///
/// Зачем это нужно. `device_id` — единственное, что связывает человека с
/// оплаченным пакетом, и до сих пор сервер верил заголовку X-Device-Id на
/// слово. Теперь личность — подписанный сервером токен, который выдаётся
/// только в обмен на заверение Apple: что запрос идёт из настоящего
/// приложения на настоящем устройстве, а не из скрипта.
///
/// Как это работает. Один раз за установку устройство создаёт ключ в защищённом
/// хранилище (Secure Enclave) и просит Apple заверить его под наш одноразовый
/// вызов. Заверение уходит на сервер, тот проверяет его целиком — цепочка
/// сертификатов до корневого Apple, вызов, отпечаток приложения — и в обмен
/// выдаёт подписанный токен. Дальше каждый запрос несёт только токен.
enum DeviceToken {

    private static let tokenKey = "proshot.device.token"
    private static let keyIdKey = "proshot.attest.keyId"
    private static let attestedKey = "proshot.device.token.attested"

    /// Токен для заголовка `X-Device-Token`. nil, пока его не получили.
    static var current: String? {
        UserDefaults.standard.string(forKey: tokenKey)
    }

    /// Заверён ли сохранённый токен. Токен, выданный сервером «на веру»,
    /// работает только пока сервер в переходном режиме.
    private static var isAttested: Bool {
        UserDefaults.standard.bool(forKey: attestedKey)
    }

    /// Получает токен, если его ещё нет или он выдан без заверения. Вызывается
    /// на старте, до первого обращения к покупкам: без токена сервер в боевом
    /// режиме откажет.
    ///
    /// Ошибку наружу не выбрасывает намеренно. Нет сети, Apple не ответила,
    /// симулятор вместо устройства — приложение всё равно должно открыться:
    /// сервер в переходном режиме принимает запросы и без токена, а в боевом
    /// человек увидит обычное сообщение о недоступности, а не пустой экран.
    static func ensure() async {
        // Выходим только если токен есть И он получен по заверению. Незаверённый
        // токен означает, что в прошлый раз что-то не сложилось — не было сети,
        // сервер ещё не умел проверять, устройство не поддерживало App Attest, —
        // и попытку надо повторить. Иначе человек, поставивший приложение до
        // включения боевого режима, остался бы незаверённым навсегда и потерял
        // бы доступ к купленному пакету в тот день, когда мы режим включим.
        if current != nil && isAttested { return }

        if let result = try? await attestedToken() {
            save(token: result.token, attested: result.attested)
            return
        }
        // Заверение не вышло. Токен всё равно нужен: без него в переходном
        // режиме приложение работает, а в боевом покажет ошибку вместо пустого
        // экрана. Признак заверения при этом не ставим — попробуем в следующий раз.
        if current == nil,
           let plain = try? await ProShotAPI.shared.deviceToken(attestation: nil) {
            save(token: plain.token, attested: plain.attested)
        }
    }

    private static func save(token: String, attested: Bool) {
        UserDefaults.standard.set(token, forKey: tokenKey)
        UserDefaults.standard.set(attested, forKey: attestedKey)
        if !attested {
            // Ключ Apple заверяет один раз. Если заверение сделано, а сервер его
            // не принял, повторять с этим же ключом бесполезно — заводим новый.
            UserDefaults.standard.removeObject(forKey: keyIdKey)
        }
    }

    /// Токен в обмен на заверение Apple. Бросает, если заверение не получилось.
    private static func attestedToken() async throws -> (token: String, attested: Bool) {
        let service = DCAppAttestService.shared
        guard service.isSupported else { throw AttestError.unsupported }

        let keyId = try await currentKeyId(service)
        let challenge = try await ProShotAPI.shared.challenge()

        // Сервер считает хэш от тех же байтов: challenge — строка, берём её UTF-8.
        let clientDataHash = Data(SHA256.hash(data: Data(challenge.utf8)))
        let attestation = try await service.attestKey(keyId, clientDataHash: clientDataHash)

        do {
            return try await ProShotAPI.shared.deviceToken(
                attestation: (keyId: keyId, attestation: attestation, challenge: challenge))
        } catch {
            // Ключ Apple заверяет ровно один раз: если сервер заверение не
            // принял, повторная попытка с этим же ключом обречена. Выбрасываем
            // ключ, чтобы следующий запуск начал с нового.
            UserDefaults.standard.removeObject(forKey: keyIdKey)
            throw error
        }
    }

    /// Идентификатор ключа: сохранённый или новый. Ключ живёт в Secure Enclave,
    /// наружу он не выходит — у нас на руках только его идентификатор.
    private static func currentKeyId(_ service: DCAppAttestService) async throws -> String {
        if let saved = UserDefaults.standard.string(forKey: keyIdKey) { return saved }
        let fresh = try await service.generateKey()
        UserDefaults.standard.set(fresh, forKey: keyIdKey)
        return fresh
    }

    enum AttestError: Error {
        /// Симулятор, или устройство без Secure Enclave, или функция выключена.
        case unsupported
    }
}
