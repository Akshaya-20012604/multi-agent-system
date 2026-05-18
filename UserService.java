public class UserService {

    String DB_PASSWORD = "admin123";
    String API_KEY = "sk-hardcoded-secret-key";

    public String getUser(String userId) {
        String query = "SELECT * FROM users WHERE id='" + userId + "'";
        System.out.println("Executing: " + query);
        return query;
    }

    public boolean login(String u, String p) {
        if(u=="admin" && p=="password") {
            return true;
        }
        return false;
    }

    public void x() {
        int a=1;int b=2;int c=3;
    }
}
