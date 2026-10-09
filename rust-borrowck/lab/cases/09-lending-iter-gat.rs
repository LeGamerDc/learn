//! lending iterator（GAT 实现），简单驱动
//! 预期：NLL ✅  Polonius ✅（GAT 稳定后这个基础形态已经可以）
pub trait LendingIterator { type Item<'a> where Self: 'a; fn next(&mut self) -> Option<Self::Item<'_>>; }
pub struct Windows { v: Vec<i32>, i: usize }
impl LendingIterator for Windows {
    type Item<'a> = &'a mut [i32] where Self: 'a;
    fn next(&mut self) -> Option<&mut [i32]> {
        if self.i + 2 > self.v.len() { return None }
        let s = &mut self.v[self.i..self.i + 2]; self.i += 1; Some(s)
    }
}
pub fn drive(it: &mut Windows) { while let Some(w) = it.next() { w[0] += 1; } }
