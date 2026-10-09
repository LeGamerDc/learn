//! 反直觉：`let _ = x` 在 move 闭包里**不会捕获** x（`_` 不是绑定，是"丢弃模式"）
//! 所以下面这段即使有 Rc 也能编译通过 —— 对比 24
//! 预期：✅（很多人会以为是 ❌）
use std::rc::Rc;
pub fn f() { let r = Rc::new(1); std::thread::spawn(move || { let _ = r; }); }
