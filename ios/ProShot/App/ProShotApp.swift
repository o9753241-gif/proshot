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
                    // Слушатель транзакций поднимается на старте приложения:
                    // покупка могла завершиться, пока приложение было закрыто.
                    purchases.start()
                    await state.bootstrap()
                }
        }
    }
}
