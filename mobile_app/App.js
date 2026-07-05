import React, { useState } from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import { API_BASE_URL, apiLogin, apiMyCards, apiSignup } from "./src/api";

const starterCards = [
  { bank: "CardPilot", name: "Save your first card", value: "Login and add cards on the website workspace." },
  { bank: "Advisor", name: "Cashback setup", value: "Heavy online spend usually starts with a cashback card." },
  { bank: "Analyzer", name: "Statement review", value: "Upload statements on the website to review rewards." }
];

function Logo() {
  return <View style={styles.logoCard}><View style={styles.logoChip} /><Text style={styles.logoText}>CP</Text></View>;
}

export default function App() {
  const [mode, setMode] = useState("login");
  const [fullName, setFullName] = useState("CardPilot User");
  const [email, setEmail] = useState("admin@cardpilot.local");
  const [password, setPassword] = useState("Admin@12345");
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [cards, setCards] = useState(starterCards);
  const [error, setError] = useState("");

  async function enter() {
    setError("");
    try {
      const data = mode === "signup" ? await apiSignup(fullName, email, password) : await apiLogin(email, password);
      setToken(data.access_token);
      setUser(data.user);
      const cardData = await apiMyCards(data.access_token).catch(() => ({ cards: [] }));
      if (cardData.cards?.length) {
        setCards(cardData.cards.map(c => ({ bank: c.bank_name, name: c.card_name, value: c.reward_currency || "Saved card" })));
      }
    } catch (e) {
      setError(e.message || "Something went wrong");
    }
  }

  if (!token) {
    return <SafeAreaView style={styles.rootDark}><StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.loginScroll}>
        <View style={styles.loginHero}>
          <Logo />
          <Text style={styles.loginTitle}>CardPilot</Text>
          <Text style={styles.loginSubtitle}>Smart credit card rewards, saved cards, and personalized recommendations from one secure account.</Text>
        </View>
        <View style={styles.loginPanel}>
          <View style={styles.modeRow}>
            <TouchableOpacity style={[styles.modePill, mode === "login" && styles.modePillActive]} onPress={() => setMode("login")}><Text style={[styles.modeText, mode === "login" && styles.modeTextActive]}>Sign in</Text></TouchableOpacity>
            <TouchableOpacity style={[styles.modePill, mode === "signup" && styles.modePillActive]} onPress={() => setMode("signup")}><Text style={[styles.modeText, mode === "signup" && styles.modeTextActive]}>Create account</Text></TouchableOpacity>
          </View>
          {mode === "signup" ? <><Text style={styles.label}>Full name</Text><TextInput value={fullName} onChangeText={setFullName} style={styles.input} /></> : null}
          <Text style={styles.label}>Email</Text><TextInput value={email} onChangeText={setEmail} style={styles.input} autoCapitalize="none" keyboardType="email-address" />
          <Text style={styles.label}>Password</Text><TextInput value={password} onChangeText={setPassword} style={styles.input} secureTextEntry />
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <TouchableOpacity style={styles.primaryButton} onPress={enter}><Text style={styles.primaryText}>{mode === "signup" ? "Create account" : "Sign in"}</Text></TouchableOpacity>
          <Text style={styles.help}>API: {API_BASE_URL}</Text>
        </View>
      </ScrollView>
    </SafeAreaView>;
  }

  return <SafeAreaView style={styles.rootLight}><StatusBar style="dark" />
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.topRow}><View><Text style={styles.eyebrow}>Welcome</Text><Text style={styles.title}>{user?.full_name || user?.email}</Text></View><Logo /></View>
      <View style={styles.heroCard}>
        <Text style={styles.heroLabel}>CardPilot Workspace</Text>
        <Text style={styles.heroTitle}>Your rewards command center</Text>
        <Text style={styles.heroValue}>Saved cards, card advisor, and reward review tools connected to your online account.</Text>
      </View>
      <View style={styles.gridRow}>
        <View style={styles.statCard}><Ionicons name="card" size={24} color="#2457ff" /><Text style={styles.statValue}>{cards.length}</Text><Text style={styles.statLabel}>Cards shown</Text></View>
        <View style={styles.statCard}><Ionicons name="shield-checkmark" size={24} color="#067647" /><Text style={styles.statValue}>Secure</Text><Text style={styles.statLabel}>Password hashing</Text></View>
      </View>
      <Text style={styles.sectionTitle}>My Cards</Text>
      {cards.map((card, idx) => <View style={styles.savedCard} key={`${card.name}-${idx}`}><View style={{ flex: 1 }}><Text style={styles.cardBank}>{card.bank}</Text><Text style={styles.cardName}>{card.name}</Text><Text style={styles.cardValue}>{card.value}</Text></View><Ionicons name="chevron-forward" size={22} color="#98a2b3" /></View>)}
      <Text style={styles.sectionTitle}>Credit Card Advisor</Text>
      <View style={styles.advisorBox}><Text style={styles.cardBank}>Profile match</Text><Text style={styles.cardName}>Build a high-value card stack</Text><Text style={styles.cardValue}>Start with one strong cashback card for daily online spend. Add travel or premium cards only when your monthly spend and travel frequency justify the annual fee.</Text></View>
      <TouchableOpacity style={styles.secondaryButton} onPress={() => { setToken(null); setUser(null); }}><Text style={styles.secondaryText}>Logout</Text></TouchableOpacity>
    </ScrollView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  rootDark:{flex:1,backgroundColor:"#071127"},rootLight:{flex:1,backgroundColor:"#f5f7fb"},loginScroll:{paddingBottom:36},container:{padding:20,paddingBottom:42},
  loginHero:{padding:28,paddingTop:54,alignItems:"center"},logoCard:{width:82,height:56,borderRadius:20,backgroundColor:"#2457ff",alignItems:"center",justifyContent:"center",shadowColor:"#2457ff",shadowOpacity:.35,shadowRadius:18,elevation:8},logoText:{color:"white",fontWeight:"900",fontSize:25,letterSpacing:-2},logoChip:{position:"absolute",left:11,top:10,width:20,height:13,borderRadius:4,backgroundColor:"#f5c451"},
  loginTitle:{fontSize:48,fontWeight:"900",color:"white",letterSpacing:-3,marginTop:18},loginSubtitle:{color:"#cbd5e1",textAlign:"center",fontSize:16,lineHeight:24,maxWidth:320},loginPanel:{margin:20,padding:22,borderRadius:30,backgroundColor:"white"},modeRow:{flexDirection:"row",backgroundColor:"#eef4ff",borderRadius:18,padding:5,marginBottom:8},modePill:{flex:1,borderRadius:14,padding:10,alignItems:"center"},modePillActive:{backgroundColor:"#2457ff"},modeText:{fontWeight:"900",color:"#667085"},modeTextActive:{color:"white"},label:{fontWeight:"800",color:"#344054",marginTop:12,marginBottom:8},input:{borderWidth:1,borderColor:"#d0d5dd",borderRadius:15,padding:13,fontSize:16},primaryButton:{marginTop:20,borderRadius:16,padding:15,alignItems:"center",backgroundColor:"#2457ff"},primaryText:{color:"white",fontWeight:"900",fontSize:16},error:{color:"#b42318",marginTop:12,fontWeight:"700"},help:{color:"#667085",marginTop:14,lineHeight:20,fontSize:12},
  topRow:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:18},eyebrow:{color:"#2457ff",fontWeight:"900",letterSpacing:2,textTransform:"uppercase"},title:{fontSize:31,fontWeight:"900",color:"#07111f",letterSpacing:-2,maxWidth:250},heroCard:{borderRadius:32,padding:24,backgroundColor:"#071127",marginBottom:16},heroLabel:{color:"#93c5fd",fontWeight:"900",textTransform:"uppercase",letterSpacing:2},heroTitle:{color:"white",fontSize:34,fontWeight:"900",letterSpacing:-2,marginTop:12},heroValue:{color:"#bfdbfe",fontSize:16,fontWeight:"700",marginTop:10,lineHeight:23},gridRow:{flexDirection:"row",gap:14},statCard:{flex:1,borderRadius:24,padding:18,backgroundColor:"white"},statValue:{fontSize:27,fontWeight:"900",color:"#07111f",marginTop:8},statLabel:{color:"#667085",fontWeight:"700"},sectionTitle:{fontSize:24,fontWeight:"900",letterSpacing:-1,color:"#07111f",marginTop:24,marginBottom:12},savedCard:{backgroundColor:"white",borderRadius:22,padding:18,marginBottom:12,flexDirection:"row",alignItems:"center",justifyContent:"space-between"},cardBank:{color:"#2457ff",fontWeight:"900"},cardName:{fontSize:18,fontWeight:"900",color:"#07111f",marginTop:4},cardValue:{color:"#667085",fontWeight:"700",lineHeight:20,marginTop:5},advisorBox:{backgroundColor:"#eef4ff",borderRadius:24,padding:18},secondaryButton:{marginTop:24,borderRadius:16,padding:15,alignItems:"center",backgroundColor:"#e2e8f0"},secondaryText:{color:"#344054",fontWeight:"900"}
});
