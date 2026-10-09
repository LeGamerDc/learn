//! 两阶段借用的边界：显式 &mut 不享受两阶段
//! 预期：NLL ❌ E0502  Polonius ❌ E0502
pub fn f() {
    let mut v = vec![1, 2, 3];
    Vec::push(&mut v, v.len());
}
