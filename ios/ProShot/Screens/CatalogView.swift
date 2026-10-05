import SwiftUI

/// Каталог целиком. Сначала сцены выбранной профессии, следом остальные —
/// ничего не спрятано, подборка только меняет порядок.
struct CatalogView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    var body: some View {
        ScreenScaffold(title: state.industryTitle,
                       subtitle: L("catalog_subtitle", state.styles.count)) {
            if state.isLoading && state.styles.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            } else if let error = state.errorMessage, state.styles.isEmpty {
                ErrorBlock(message: error) { Task { await state.bootstrap() } }
            } else {
                let recommended = state.recommended(from: state.styles)
                let others = state.others(from: state.styles)

                if !recommended.isEmpty {
                    SceneSection(title: L("catalog_recommended"),
                                 note: L("catalog_recommended_note"),
                                 scenes: recommended)
                }
                if !others.isEmpty {
                    SceneSection(title: recommended.isEmpty ? L("catalog_all") : L("catalog_other"),
                                 note: nil,
                                 scenes: others)
                }
            }
        } bottom: {
            PrimaryButton(title: L("catalog_continue"),
                          enabled: !state.styles.isEmpty) {
                path.append(.packages)
            }
        }
    }
}

/// Озаглавленный кусок каталога.
private struct SceneSection: View {
    let title: String
    let note: String?
    let scenes: [StyleDTO]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(.inter(20, .semibold))
                Spacer()
                Text(L("catalog_count", scenes.count))
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
            }
            if let note {
                Text(note)
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            SceneList(scenes: scenes)
        }
        .padding(.top, 8)
    }
}

/// Крупные карточки сцен по одной в ряд, как StyleCardLarge в Android:
/// превью 4:3 на всю ширину, затемнение снизу, название белым поверх.
/// Каталог и выбор сцен. Сетка из мелких превью (SceneGrid) осталась
/// только там, где она и в Android: превью заказа и экран результата.
struct SceneList: View {
    let scenes: [StyleDTO]
    /// Выбранные ключи по порядку выбора: номер на карточке = место в списке.
    var selectedOrder: [String] = []
    /// Можно ли выбрать ещё одну сцену. Невыбранные карточки при false гаснут.
    var canPickMore: Bool = true
    var onTap: ((String) -> Void)?

    var body: some View {
        LazyVStack(spacing: 12) {
            ForEach(scenes) { scene in
                let index = selectedOrder.firstIndex(of: scene.key)
                SceneCardLarge(title: scene.title,
                               previewUrl: scene.previewUrl,
                               selectedNumber: index.map { $0 + 1 },
                               dimmed: onTap != nil && index == nil && !canPickMore)
                    .onTapGesture { onTap?(scene.key) }
            }
        }
    }
}

struct SceneCardLarge: View {
    let title: String
    let previewUrl: String
    var selectedNumber: Int?
    var dimmed: Bool = false

    var body: some View {
        CachedImage(url: URL(string: previewUrl)) {
            Rectangle().fill(Palette.fill)
        }
        .croppedTo(aspect: 4.0 / 3.0)
        .overlay {
            LinearGradient(colors: [.clear, .black.opacity(0.65)],
                           startPoint: UnitPoint(x: 0.5, y: 0.45), endPoint: .bottom)
        }
        .overlay(alignment: .bottomLeading) {
            Text(title)
                .font(.inter(20, .semibold))
                .foregroundStyle(.white)
                .lineLimit(2)
                .padding(.horizontal, 18).padding(.vertical, 14)
        }
        .overlay(alignment: .topTrailing) {
            if let selectedNumber {
                Text("\(selectedNumber)")
                    .font(.inter(15, .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 8))
                    .padding(12)
            }
        }
        .overlay {
            if dimmed { Color.black.opacity(0.35) }
        }
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay {
            RoundedRectangle(cornerRadius: 18)
                .strokeBorder(selectedNumber != nil ? Color.accentColor : .clear, lineWidth: 3)
        }
        .contentShape(RoundedRectangle(cornerRadius: 18))
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selectedNumber != nil ? [.isButton, .isSelected] : .isButton)
    }
}

/// Сетка мелких превью сцен: превью заказа и экран результата (как в Android).
struct SceneGrid: View {
    let scenes: [StyleDTO]
    var selected: Set<String> = []
    var onTap: ((String) -> Void)?

    // Три колонки, как в Android (SummaryScreen: GridCells.Fixed(3)), по верху:
    // при выравнивании по центру карточка с подписью в одну строку съезжала
    // ниже соседних с подписью в две.
    private let columns = Array(repeating: GridItem(.flexible(), spacing: 10, alignment: .top),
                                count: 3)

    var body: some View {
        LazyVGrid(columns: columns, spacing: 10) {
            ForEach(scenes) { scene in
                VStack(spacing: 6) {
                    ZStack(alignment: .topTrailing) {
                        CachedImage(url: URL(string: scene.previewUrl)) {
                            Rectangle().fill(.quaternary)
                        }
                        .croppedTo(aspect: 1)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .overlay {
                            RoundedRectangle(cornerRadius: 10)
                                .strokeBorder(selected.contains(scene.key) ? Color.accentColor : .clear,
                                              lineWidth: 3)
                        }

                        if selected.contains(scene.key) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(.white, Color.accentColor)
                                .padding(6)
                        }
                    }
                    Text(scene.title)
                        .font(.inter(11))
                        .lineLimit(2, reservesSpace: true)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                }
                .contentShape(Rectangle())
                .onTapGesture { onTap?(scene.key) }
            }
        }
    }
}

struct ErrorBlock: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Text(message).font(.inter(14)).multilineTextAlignment(.center)
            Button(L("retry"), action: retry).buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
}
