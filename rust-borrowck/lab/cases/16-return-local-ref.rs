//! 返回局部变量的引用：这是真正的悬垂引用，永远不会被接受
//! 预期：NLL ❌ E0515  Polonius ❌ E0515
pub fn f() -> &'static String { let s = String::from("x"); &s }
