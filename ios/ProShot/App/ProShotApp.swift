import SwiftUI

@main
@MainActor
struct ProShotApp: App {
    @StateObject private var state = AppState()
    @StateObject private var purchases = PurchaseManager()

    // SwiftUI.Scene полностью: в модуле может оказаться свой тип Scene,
    // и тогда короткая запись ломается — в Starshot так и случилось.
    var body: some SwiftUI.Scene {
        WindowGroup {
            RootView()
                .environmentObject(state)
                .environmentObject(purchases)
                .task {
                    // Сначала токен устройства: без него сервер в боевом режиме
                    // не примет ни покупку, ни генерацию (см. AppAttest.swift).
                    await DeviceToken.ensure()
                    // Слушатель транзакций поднимается на старте приложения:
                    // покупка могла завершиться, пока приложение было закрыто.
                    // После токена — восстановление незакрытой покупки сразу
                    // идёт на сервер с ним.
                    purchases.start()
                    await state.bootstrap()
                }
        }
    }
}
