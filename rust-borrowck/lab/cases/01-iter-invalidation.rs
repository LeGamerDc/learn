//! 迭代器失效：Rust 版的 C++/Java 经典 bug
//! 预期：NLL ❌ E0502  Polonius ❌ E0502（真·别名冲突，两者都该拒绝）
pub fn f() {
    let mut v = vec![1, 2, 3];
    for x in &v {
        if *x == 2 { v.push(99); }
    }
}
