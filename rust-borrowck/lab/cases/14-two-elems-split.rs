//! 同一件事的正确写法：split_at_mut 把"不相交"这个事实交给一个 unsafe 的库函数去保证
//! 预期：NLL ✅  Polonius ✅
pub fn f(v: &mut Vec<i32>) { let (l, r) = v.split_at_mut(1); l[0] += r[0]; }
