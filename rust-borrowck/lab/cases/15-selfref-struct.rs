//! 自引用结构：结构体的一个字段引用另一个字段
//! 预期：NLL ❌ E0505  Polonius ❌ E0505（需要"内部引用"，见第 17 章）
pub struct S<'a> { data: String, view: &'a str }
pub fn f() { let d = String::from("hello"); let _s = S { view: &d, data: d }; }
