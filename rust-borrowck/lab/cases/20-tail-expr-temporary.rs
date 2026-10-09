//! 2024 edition 改变了尾表达式临时值的 drop 顺序
//! 预期（2024 edition）：✅  在 2021 edition 下报 E0597
use std::cell::RefCell;
pub fn f() -> i32 { let c = RefCell::new(5); *c.borrow() }
