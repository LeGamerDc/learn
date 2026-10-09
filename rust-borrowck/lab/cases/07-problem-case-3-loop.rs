//! NLL problem case #3 的 loop 版本（历史上更难，需要跨循环迭代的流敏感）
//! 预期：NLL ❌ E0499  Polonius ✅
use std::collections::HashMap; use std::hash::Hash;
pub fn f<'r, K: Hash + Eq + Copy, V: Default>(map: &'r mut HashMap<K, V>, key: K) -> &'r mut V {
    loop {
        match map.get_mut(&key) {
            Some(v) => return v,
            None => { map.insert(key, V::default()); }
        }
    }
}
