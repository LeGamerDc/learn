//! 条件重借用：官方博客里的最小例子
//! 预期：NLL ❌ E0499  Polonius ✅
pub fn f(a: &mut u8) -> &mut u8 {
    let b = &mut *a;
    if *b > 0 { b } else { a }
}
