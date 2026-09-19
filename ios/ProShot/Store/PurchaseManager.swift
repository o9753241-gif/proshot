import Foundation
import StoreKit

/// Покупки через StoreKit 2.
///
/// Порядок ровно тот же, что в Android-версии (ProShotBilling.kt), и он важен:
///
///   1. Apple проводит оплату и отдаёт подписанную транзакцию.
///   2. Транзакция уходит на НАШ сервер, тот проверяет подпись и начисляет фото.
///   3. И только потом транзакция закрывается через `finish()`.
///
/// Обратный порядок теряет деньги: если закрыть транзакцию до ответа сервера и
/// в этот момент связи не будет, восстанавливать станет нечем. Незакрытую
/// транзакцию Apple принесёт снова — в том числе после перезапуска приложения.
@MainActor
final class PurchaseManager: ObservableObject {

    enum Outcome {
        case success(PurchaseDTO)
        case cancelled
        /// Оплата ушла в отложенное состояние (родительский контроль и подобное).
        case pending
        case failed(String)
    }

    @Published private(set) var products: [Product] = []
    @Published private(set) var isLoading = false
    /// Последняя известная активная покупка — её отдаёт сервер, не StoreKit.
    private(set) var activePurchase: PurchaseDTO?

    private var updatesTask: Task<Void, Never>?

    // MARK: - Жизненный цикл

    /// Вызывается при старте приложения, а не при открытии пейволла.
    /// Иначе транзакция, пришедшая после перезапуска, останется необработанной.
    func start() {
        updatesTask = Task.detached(priority: .background) { [weak self] in
            for await update in Transaction.updates {
                await self?.settle(update, scenes: nil)
            }
        }
        Task { await recoverUnfinished() }
    }

    deinit { updatesTask?.cancel() }

    func loadProducts() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let loaded = try await Product.products(for: Config.productIDs)
            // Порядок из Config, а не тот, в котором ответил StoreKit.
            products = Config.productIDs.compactMap { id in
                loaded.first { $0.id == id }
            }
        } catch {
            products = []
        }
    }

    // MARK: - Покупка

    /// - Parameter scenes: выбранные сцены. Сервер проверит их количество
    ///   против `max_scenes` пакета и откажет, если не сходится.
    func purchase(_ product: Product, scenes: [String]) async -> Outcome {
        do {
            // appAccountToken связывает покупку с нашим пользователем: сервер
            // получит этот UUID внутри проверенной транзакции.
            let token = UUID(uuidString: DeviceID.current) ?? UUID()
            let result = try await product.purchase(options: [.appAccountToken(token)])

            switch result {
            case .success(let verification):
                return await settle(verification, scenes: scenes)
            case .userCancelled:
                return .cancelled
            case .pending:
                return .pending
            @unknown default:
                return .failed("Неизвестный ответ App Store.")
            }
        } catch {
            return .failed(error.localizedDescription)
        }
    }

    /// Незавершённые транзакции: деньги списаны, а фото ещё не начислены.
    /// Прямой аналог `pendingPurchases()` из Android-версии.
    func recoverUnfinished() async {
        for await transaction in Transaction.unfinished {
            _ = await settle(transaction, scenes: nil)
        }
    }

    // MARK: - Общий путь для всех источников транзакций

    @discardableResult
    private func settle(_ verification: VerificationResult<Transaction>,
                        scenes: [String]?) async -> Outcome {
        // Подпись проверяет и клиент, и сервер. Клиентская проверка отсекает
        // явный мусор до сетевого запроса, но решающей считается серверная.
        guard case .verified(let transaction) = verification else {
            return .failed("Транзакция не прошла проверку подписи.")
        }

        let selected = scenes ?? recoveredScenes(for: transaction)
        guard !selected.isEmpty else {
            // Сервер требует от одной сцены. Транзакцию НЕ закрываем: она
            // вернётся, когда человек выберет сцены на экране.
            return .failed("Выберите сцены, чтобы получить оплаченные фото.")
        }

        do {
            let purchase = try await ProShotAPI.shared.verifyPurchase(
                sku: transaction.productID,
                signedTransaction: verification.jwsRepresentation,
                scenes: selected
            )
            // Сервер начислил фото — только теперь закрываем транзакцию.
            await transaction.finish()
            SceneSelectionStore.clear(for: transaction.productID)
            activePurchase = purchase
            return .success(purchase)
        } catch {
            // Транзакция НЕ закрывается: Apple принесёт её снова, и попытка
            // повторится при следующем запуске.
            let message = (error as? APIError)?.errorDescription
                ?? "Не удалось начислить фото. Попробуем ещё раз при следующем запуске."
            return .failed(message)
        }
    }

    /// Сцены для транзакции, которую принесла Apple без участия экрана покупки.
    ///
    /// Сервер требует непустой список и проверяет его против `max_scenes`.
    /// Выбор пользователя сохраняется на экране выбора сцен, оттуда и берётся;
    /// если его нет — восстановление отложится до открытия приложения, где
    /// человек выберет сцены заново.
    private func recoveredScenes(for transaction: Transaction) -> [String] {
        SceneSelectionStore.saved(for: transaction.productID)
    }
}

/// Выбор сцен переживает перезапуск: между оплатой и ответом сервера
/// приложение может закрыться, а серверу этот список нужен.
enum SceneSelectionStore {
    private static func key(_ sku: String) -> String { "proshot.scenes.\(sku)" }

    static func save(_ scenes: [String], for sku: String) {
        UserDefaults.standard.set(scenes, forKey: key(sku))
    }

    static func saved(for sku: String) -> [String] {
        UserDefaults.standard.stringArray(forKey: key(sku)) ?? []
    }

    static func clear(for sku: String) {
        UserDefaults.standard.removeObject(forKey: key(sku))
    }
}
