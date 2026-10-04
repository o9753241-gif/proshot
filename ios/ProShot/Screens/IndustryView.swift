import SwiftUI

/// Первый экран: кем человек работает.
///
/// Полсотни сцен списком — это витрина, а не инструмент. Отрасль сразу
/// сужает каталог до уместного: юристу не нужен киберпанк, разработчику —
/// гала-ужин. Выбор ни к чему не обязывает, «Все сцены» рядом.
struct IndustryView: View {
    @Binding var path: [Route]
    @EnvironmentObject private var state: AppState

    // Две колонки с выравниванием по верху: при .adaptive и выравнивании по
    // центру карточка с названием в две строки делала соседнюю ниже на полстроки.
    private let columns = [GridItem(.flexible(), spacing: 12, alignment: .top),
                           GridItem(.flexible(), spacing: 12, alignment: .top)]

    var body: some View {
        ScreenScaffold(title: L("industry_title"), subtitle: L("industry_subtitle")) {
            if state.isLoading && state.industries.isEmpty {
                ProgressView().frame(maxWidth: .infinity).padding(.vertical, 40)
            } else if let error = state.errorMessage, state.industries.isEmpty {
                ErrorBlock(message: error) { Task { await state.bootstrap() } }
            } else {
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(state.industries) { industry in
                        IndustryCard(title: industry.title,
                                     note: L("industry_scenes", industry.sceneCount),
                                     previewUrl: industry.previewUrl) {
                            state.selectIndustry(industry.key)
                            path.append(.catalog)
                        }
                    }
                }

                Button {
                    state.selectIndustry(nil)
                    path.append(.catalog)
                } label: {
                    HStack {
                        Text(L("industry_all")).font(.inter(16, .semibold))
                        Spacer()
                        Image(systemName: "chevron.right").font(.inter(13))
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity)
                    .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .padding(.top, 4)

                Text(L("industry_hint"))
                    .font(.inter(12))
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 4)
            }
        }
    }
}

private struct IndustryCard: View {
    let title: String
    let note: String
    let previewUrl: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 0) {
                CachedImage(url: URL(string: previewUrl)) {
                    Rectangle().fill(.quaternary)
                }
                .croppedTo(aspect: 4.0 / 3.0)
                .frame(maxWidth: .infinity)

                VStack(alignment: .leading, spacing: 3) {
                    // Место под две строки резервируется всегда: карточки
                    // в ряду одной высоты, даже если название в одну строку.
                    Text(title)
                        .font(.inter(15, .semibold))
                        .multilineTextAlignment(.leading)
                        .lineLimit(2, reservesSpace: true)
                    Text(note).font(.inter(11)).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
            }
            .background(Palette.fill, in: RoundedRectangle(cornerRadius: 14))
            .clipShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
    }
}
