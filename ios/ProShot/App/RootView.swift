import SwiftUI

/// Маршруты повторяют Routes.kt Android-версии, порядок тот же.
enum Route: Hashable {
    case catalog, packages, scenes, summary, upload, result, gallery
}

struct RootView: View {
    @EnvironmentObject private var state: AppState
    @State private var path: [Route] = []
    @State private var showOnboarding = false

    var body: some View {
        NavigationStack(path: $path) {
            CatalogView(path: $path)
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .catalog:  CatalogView(path: $path)
                    case .packages: PackagesView(path: $path)
                    case .scenes:   ScenesView(path: $path)
                    case .summary:  SummaryView(path: $path)
                    case .upload:   UploadView(path: $path)
                    case .result:   ResultView(path: $path)
                    case .gallery:  GalleryView()
                    }
                }
        }
        .fullScreenCover(isPresented: $showOnboarding) {
            OnboardingView { showOnboarding = false }
        }
        .onAppear {
            if state.needsOnboarding {
                showOnboarding = true
                state.needsOnboarding = false
            }
        }
    }
}
