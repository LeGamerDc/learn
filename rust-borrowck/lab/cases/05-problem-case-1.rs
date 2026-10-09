//! NLL problem case #1：match 一个分支借用、另一个分支修改
//! 预期：NLL ❌ E0502  Polonius ✅
pub fn f(v: &mut Vec<i32>) -> &i32 {
    match v.first() {
        Some(x) => x,
        None => { v.push(1); v.first().unwrap() }
    }
}
