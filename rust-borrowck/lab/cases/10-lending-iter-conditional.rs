//! lending iterator + 条件返回：这才是 NLL 真正卡住的形态
//! 预期：NLL ❌  Polonius ✅
pub trait LendingIterator { type Item<'a> where Self: 'a; fn next(&mut self) -> Option<Self::Item<'_>>; }
pub struct Windows { v: Vec<i32>, i: usize }
impl LendingIterator for Windows {
    type Item<'a> = &'a mut [i32] where Self: 'a;
    fn next(&mut self) -> Option<&mut [i32]> {
        if self.i + 2 > self.v.len() { return None }
        let s = &mut self.v[self.i..self.i + 2]; self.i += 1; Some(s)
    }
}
/// 找到第一个满足条件的窗口并把它返回出去
pub fn find_mut(it: &mut Windows) -> Option<&mut [i32]> {
    loop {
        match it.next() {
            Some(w) => { if w[0] > 0 { return Some(w); } }
            None => return None,
        }
    }
}
