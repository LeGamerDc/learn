//! 两阶段借用：v.push(v.len()) 为什么能过
//! 预期：NLL ✅  Polonius ✅
pub fn f() {
    let mut v = vec![1, 2, 3];
    v.push(v.len());          // autoref 的 &mut v 先"预留"，参数求值时仍算共享借用
}
