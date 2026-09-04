import SwiftUI

@main
@MainActor
struct ProShotApp: App {
    @State private var state = AppState()
    @State private var purchases = PurchaseManager()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(state)
                .environment(purchases)
                .task {
                    // Слушатель транзакций поднимается на старте приложения:
                    // покупка могла завершиться, пока приложение было закрыто.
                    purchases.start()
                    await state.bootstrap()
                }
        }
    }
}
