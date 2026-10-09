//! 跨 await 持有借用：借用本身没问题，问题在 Send
//! 预期：✅（单看借用检查）
pub async fn f(v: &mut Vec<i32>) { let first = &v[0]; tokio_like().await; println!("{}", first); }
async fn tokio_like() {}
