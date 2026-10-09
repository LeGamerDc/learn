//! 同时可变借用同一个 Vec 的两个元素
//! 预期：NLL ❌ E0499  Polonius ❌ E0499（索引不是 place，编译器无法证明不相交）
pub fn f(v: &mut Vec<i32>) { let a = &mut v[0]; let b = &mut v[1]; *a += *b; }
