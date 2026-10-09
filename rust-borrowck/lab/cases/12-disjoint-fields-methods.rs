//! 字段分割借用：一旦通过 &self / &mut self 方法访问，字段粒度就丢失了
//! 预期：NLL ❌ E0502  Polonius ❌ E0502（需要 view types，见第 17 章）
pub struct S { a: Vec<i32>, b: Vec<i32> }
impl S { fn get_a(&self) -> &Vec<i32> { &self.a } fn push_b(&mut self, x: i32) { self.b.push(x) } }
pub fn f(s: &mut S) { let a = s.get_a(); s.push_b(a.len() as i32); println!("{}", a.len()); }
