import Foundation

/// Короткая обёртка над NSLocalizedString.
/// Ключи и тексты перенесены из Android-версии без изменений.
func L(_ key: String) -> String {
    NSLocalizedString(key, comment: "")
}

func L(_ key: String, _ args: CVarArg...) -> String {
    String(format: NSLocalizedString(key, comment: ""), arguments: args)
}
