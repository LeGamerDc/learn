//! thread::spawn 要求 'static：借用局部变量会被拒绝
//! 预期：NLL ❌ E0373  Polonius ❌ E0373
pub fn f() {
    let v = vec![1, 2, 3];
    std::thread::spawn(|| println!("{:?}", v));
}
