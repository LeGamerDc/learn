//! 字段分割借用：直接访问字段是 OK 的
//! 预期：NLL ✅  Polonius ✅
pub struct S { a: Vec<i32>, b: Vec<i32> }
pub fn f(s: &mut S) { let a = &s.a; s.b.push(a.len() as i32); println!("{}", a.len()); }
