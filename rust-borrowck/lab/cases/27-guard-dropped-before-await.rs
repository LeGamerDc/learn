//! 同一件事：把 guard 的作用域收缩到 await 之前，Future 重新变成 Send
//! 预期：✅
use std::sync::Mutex;
fn assert_send<T: Send>(_: T) {}
async fn yield_now() {}
async fn good(m: &Mutex<i32>) { let v = { *m.lock().unwrap() }; yield_now().await; println!("{}", v); }
pub fn f(m: &'static Mutex<i32>) { assert_send(good(m)); }
