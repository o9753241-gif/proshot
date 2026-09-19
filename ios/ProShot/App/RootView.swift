import SwiftUI

/// Порядок прохода: отрасль → каталог → тариф → сцены → оплата →
/// съёмка трёх кадров → результат → кадрировки.
enum Route: Hashable {
    case industry, catalog, packages, scenes, summary, capture, result, cropSet, gallery
}

struct RootView: View {
    @EnvironmentObject private var state: AppState
    @State private var path: [Route] = []
    @State private var showOnboarding = false

    var body: some View {
        NavigationStack(path: $path) {
            IndustryView(path: $path)
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .industry: IndustryView(path: $path)
                    case .catalog:  CatalogView(path: $path)
                    case .packages: PackagesView(path: $path)
                    case .scenes:   ScenesView(path: $path)
                    case .summary:  SummaryView(path: $path)
                    case .capture:  CaptureView(path: $path)
                    case .result:   ResultView(path: $path)
                    case .cropSet:  CropSetView(path: $path)
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
