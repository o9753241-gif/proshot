import Foundation

/// Короткая обёртка над NSLocalizedString.
/// Ключи и тексты перенесены из Android-версии без изменений.
func L(_ key: String) -> String {
    NSLocalizedString(key, comment: "")
}

func L(_ key: String, _ args: CVarArg...) -> String {
    // locale: — чтобы формы множественного числа из Localizable.stringsdict
    // («3 сцены», «1 scene») выбирались по правилам языка пользователя.
    String(format: NSLocalizedString(key, comment: ""), locale: Locale.current, arguments: args)
}
