//! Rc 不是 Send：借用规则在线程维度的直接推广
//! 预期：❌ E0277（注意：必须真正"使用" r 才会捕获，见 25）
use std::rc::Rc;
pub fn f() { let r = Rc::new(1); std::thread::spawn(move || { println!("{}", r); }); }
